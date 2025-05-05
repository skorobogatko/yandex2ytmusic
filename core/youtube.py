import os
import webbrowser
import time
import json
import urllib.parse
import traceback
import logging
import re
from typing import List, Tuple, Optional, Dict
from tqdm import tqdm
from ytmusicapi import YTMusic, setup
from ytmusicapi.parsers.library import parse_content_list
from .track import Track

logger = logging.getLogger(__name__)

class YoutubeImoirter:
    def __init__(self, token_path: str):
        if not os.path.exists(token_path):
            print(f"Файл учетных данных '{token_path}' не найден. Запускается настройка...")
            try:
                auth_url = setup(filepath=token_path, open_browser=False)
                print(f"Перейдите по следующей ссылке для авторизации: {auth_url}")
                webbrowser.open(auth_url)
                input("После завершения авторизации нажмите Enter для продолжения...")
                print(f"Настройка завершена. Учетные данные сохранены в '{token_path}'.")
            except Exception as e:
                print(f"Ошибка во время настройки YouTube Music: {e}")
                raise

        try:
            self.ytmusic = YTMusic(auth=token_path)
            print("Аутентификация в YouTube Music прошла успешно.")
        except Exception as e:
            print(f"Ошибка при инициализации YTMusic с файлом '{token_path}': {e}")
            print("Попробуйте удалить файл '{token_path}' и запустить скрипт заново.")
            raise

    def import_liked_tracks(self, tracks: List[Track]) -> Tuple[List[Track], List[Track]]:
        not_found = []
        errors = []
        with tqdm(total=len(tracks), desc='Импорт треков') as pbar:
            for track in tracks:
                try:
                    query = f'{track.artist} {track.name}'
                    print(f"Отправляю запрос: {query}")
                    for attempt in range(3):
                        try:
                            results = self.ytmusic.search(query)
                            break
                        except json.JSONDecodeError as e:
                            last_response = self.ytmusic._session.hooks['response'][-1] if self.ytmusic._session.hooks.get('response') else None
                            if last_response:
                                print(f"Ошибка JSON при попытке {attempt + 1}: {e}")
                                print(f"Статус код ответа: {last_response.status_code}")
                                print(f"Текст ответа: {last_response.text[:500]}...")
                            else:
                                print(f"Ошибка JSON при попытке {attempt + 1}, но не удалось получить ответ из сессии.")
                            if attempt < 2:
                                time.sleep(5)
                            else:
                                raise
                    else:
                        results = None
                        print(f"Не удалось получить результаты для {query} после всех попыток.")

                    if not results:
                        not_found.append(track)
                        pbar.write(f'Не найдено: {track.artist} - {track.name}')
                        pbar.set_description_str(f'Импорт треков: {track.artist} - {track.name} (Не найдено)')
                        pbar.update()
                        continue

                    result = self._get_best_result(results, track)
                    if not result:
                        not_found.append(track)
                        pbar.write(f'Не найдено: {track.artist} - {track.name}')
                        pbar.set_description_str(f'Импорт треков: {track.artist} - {track.name} (Нет подходящего результата)')
                        pbar.update()
                        continue

                    try:
                        self.ytmusic.rate_song(result['videoId'], 'LIKE')
                        pbar.set_description_str(f'Импорт треков: Лайкнуто {track.artist} - {track.name}')
                    except Exception as e:
                        errors.append(track)
                        pbar.write(f'Ошибка: {track.artist} - {track.name}, {e}')
                        pbar.set_description_str(f'Импорт треков: Ошибка {track.artist} - {track.name}')

                except Exception as e:
                    errors.append(track)
                    pbar.write(f'Ошибка во время поиска: {track.artist} - {track.name}, {e}')
                    pbar.set_description_str(f'Импорт треков: Ошибка во время поиска {track.artist} - {track.name}')
                    traceback.print_exc()

                pbar.update()
                time.sleep(1)

        return not_found, errors

    def _get_best_result(self, results: List[dict], track: Track) -> Optional[dict]:
        songs = []
        if not results:
            return None

        for result in results:
            if 'videoId' not in result.keys():
                continue
            if result['category'] == 'Top result':
                return result
            if result['title'] == track.name:
                return result
            songs.append(result)
        if songs:
            return songs[0]
        return results[0]

    def import_playlists(self, playlists_data: Dict[str, List[Track]]) -> Dict:
        """Импортирует плейлисты и их треки в YouTube Music."""
        report = {
            "playlists_created": [],
            "playlists_existing": [],
            "playlists_failed": [],
            "overall_stats": {
                "total_playlists_processed": len(playlists_data),
                "total_tracks_processed": 0,
                "total_tracks_added": 0,
                "total_tracks_not_found": 0,
                "total_errors": 0
            }
        }

        existing_playlists_map = {}
        try:
            logger.info("Fetching existing YouTube Music playlists...")
            results = self.ytmusic.get_library_playlists(limit=500)

            if results is None:
                logger.error("Failed to fetch existing playlists from YouTube Music. API returned None.")
                existing_playlists_map = {}
            elif "items" not in results or not isinstance(results.get("items"), list):
                logger.warning(f"YouTube Music API response for playlists is missing 'items' or it's not a list: {results}")
                existing_playlists_map = {}
            elif len(results["items"]) < 2:
                logger.warning(f"YouTube Music API response 'items' list is too short for expected parsing: {results}")
                existing_playlists_map = {}
            else:
                playlists = parse_content_list(results["items"][1:])
                existing_playlists_map = {p['title']: p['playlistId'] for p in playlists}
                logger.info(f"Found {len(existing_playlists_map)} existing playlists.")

        except Exception as e:
            logger.error(f"An error occurred while fetching or parsing existing YouTube playlists: {e}")
            logger.error(traceback.format_exc())
            existing_playlists_map = {}

        for playlist_title, tracks in playlists_data.items():
            print(f"\nProcessing playlist '{playlist_title}' for import...")
            playlist_report = {
                "title": playlist_title,
                "status": "pending",
                "youtube_playlist_id": None,
                "tracks_added_count": 0,
                "tracks_not_found_count": 0,
                "tracks_error_count": 0,
                "tracks_not_found_details": [],
                "tracks_error_details": []
            }

            if isinstance(tracks, dict) and "error" in tracks:
                print(f"Skipping playlist '{playlist_title}' due to previous export error: {tracks['error']}")
                playlist_report["status"] = f"skipped_export_error: {tracks['error']}"
                report["playlists_failed"].append(playlist_report)
                report["overall_stats"]["total_errors"] += 1
                continue

            if not isinstance(tracks, list):
                print(f"Skipping playlist '{playlist_title}' due to invalid track data format.")
                playlist_report["status"] = "skipped_invalid_data"
                report["playlists_failed"].append(playlist_report)
                report["overall_stats"]["total_errors"] += 1
                continue

            report["overall_stats"]["total_tracks_processed"] += len(tracks)

            try:
                yt_playlist_id = None
                if playlist_title in existing_playlists_map:
                    yt_playlist_id = existing_playlists_map[playlist_title]
                    print(f"Playlist '{playlist_title}' already exists with ID: {yt_playlist_id}. Adding tracks to it.")
                    playlist_report["status"] = "existing"
                    report["playlists_existing"].append(playlist_report)
                else:
                    print(f"Creating new playlist '{playlist_title}'...")
                    creation_result = self.ytmusic.create_playlist(title=playlist_title, description=f"Imported from Yandex Music", privacy_status='PRIVATE')
                    if isinstance(creation_result, str):
                        yt_playlist_id = creation_result
                    elif isinstance(creation_result, dict) and 'playlistId' in creation_result:
                        yt_playlist_id = creation_result['playlistId']
                    else:
                        raise Exception(f"Failed to create playlist. API response: {creation_result}")

                    print(f"Playlist '{playlist_title}' created with ID: {yt_playlist_id}")
                    playlist_report["status"] = "created"
                    report["playlists_created"].append(playlist_report)

                playlist_report["youtube_playlist_id"] = yt_playlist_id

            except Exception as e:
                print(f"Error creating/finding playlist '{playlist_title}': {e}")
                traceback.print_exc()
                playlist_report["status"] = f"failed_creation: {e}"
                report["playlists_failed"].append(playlist_report)
                report["overall_stats"]["total_errors"] += 1
                continue

            video_ids_to_add = []
            with tqdm(total=len(tracks), desc=f"Finding tracks for '{playlist_title}'", leave=False) as pbar:
                for track in tracks:
                    try:
                        query = f'{track.artist} {track.name}'
                        search_results = None
                        for attempt in range(3):
                            try:
                                search_results = self.ytmusic.search(query, filter='songs')
                                break
                            except json.JSONDecodeError as json_e:
                                last_response = self.ytmusic._session.hooks['response'][-1] if self.ytmusic._session.hooks.get('response') else None
                                pbar.write(f"Warning: JSON error searching for '{query}' (Attempt {attempt + 1}): {json_e}. Response status: {last_response.status_code if last_response else 'N/A'}")
                                if attempt < 2:
                                    time.sleep(3)
                                else:
                                    raise
                            except Exception as search_e:
                                pbar.write(f"Warning: Error searching for '{query}' (Attempt {attempt + 1}): {search_e}")
                                if attempt < 2:
                                    time.sleep(3)
                                else:
                                    raise

                        if not search_results:
                            pbar.write(f"Not found: {track.artist} - {track.name}")
                            playlist_report["tracks_not_found_count"] += 1
                            playlist_report["tracks_not_found_details"].append({'artist': track.artist, 'name': track.name})
                            report["overall_stats"]["total_tracks_not_found"] += 1
                            pbar.update(1)
                            continue

                        best_result = self._get_best_result(search_results, track)

                        if best_result and 'videoId' in best_result:
                            video_ids_to_add.append(best_result['videoId'])
                        else:
                            pbar.write(f"Not found (no suitable result): {track.artist} - {track.name}")
                            playlist_report["tracks_not_found_count"] += 1
                            playlist_report["tracks_not_found_details"].append({'artist': track.artist, 'name': track.name})
                            report["overall_stats"]["total_tracks_not_found"] += 1

                    except Exception as e:
                        pbar.write(f"Error processing track '{track.artist} - {track.name}': {e}")
                        playlist_report["tracks_error_count"] += 1
                        playlist_report["tracks_error_details"].append({'artist': track.artist, 'name': track.name, 'error': str(e)})
                        report["overall_stats"]["total_errors"] += 1
                    finally:
                        pbar.update(1)
                        time.sleep(0.5)

            if video_ids_to_add:
                print(f"Adding {len(video_ids_to_add)} found tracks to playlist '{playlist_title}' ({yt_playlist_id})...")
                try:
                    chunk_size = 50
                    added_count_in_playlist = 0
                    for i in range(0, len(video_ids_to_add), chunk_size):
                        chunk = video_ids_to_add[i:i + chunk_size]
                        add_result = self.ytmusic.add_playlist_items(playlistId=yt_playlist_id, videoIds=chunk, duplicates=True)

                        if add_result.get('status') == 'STATUS_SUCCEEDED' or 'actions' in add_result:
                            actual_added = len([action for action in add_result.get('actions', []) if action.get('action') == 'ACTION_ADD_VIDEO'])
                            added_count_in_playlist += actual_added
                            print(f"Successfully added chunk {i//chunk_size + 1} ({actual_added} tracks) to '{playlist_title}'.")
                        else:
                            print(f"Warning: Failed to add chunk {i//chunk_size + 1} to '{playlist_title}'. Response: {add_result}")
                            playlist_report["tracks_error_count"] += len(chunk)
                            report["overall_stats"]["total_errors"] += len(chunk)

                        time.sleep(1)

                    playlist_report["tracks_added_count"] = added_count_in_playlist
                    report["overall_stats"]["total_tracks_added"] += added_count_in_playlist
                    print(f"Finished adding tracks to '{playlist_title}'. Total added: {added_count_in_playlist}")

                except Exception as e:
                    print(f"Error adding tracks in bulk to playlist '{playlist_title}': {e}")
                    traceback.print_exc()
                    if playlist_report["status"] in ["created", "existing"]:
                        playlist_report["status"] += "_with_add_errors"
                    playlist_report["tracks_error_count"] += len(video_ids_to_add)
                    report["overall_stats"]["total_errors"] += len(video_ids_to_add)
            else:
                print(f"No tracks found to add to playlist '{playlist_title}'.")

            if playlist_report["status"] not in ["failed_creation", "skipped_export_error", "skipped_invalid_data"]:
                if playlist_report["tracks_error_count"] > 0:
                    playlist_report["status"] += "_partial_error"
                elif playlist_report["tracks_not_found_count"] > 0 and playlist_report["tracks_added_count"] > 0:
                    playlist_report["status"] += "_partial_not_found"
                elif playlist_report["tracks_not_found_count"] == len(tracks) and len(tracks) > 0:
                    playlist_report["status"] += "_all_not_found"
                elif playlist_report["tracks_added_count"] == len(tracks):
                    playlist_report["status"] += "_complete"

            time.sleep(2)

        return report
