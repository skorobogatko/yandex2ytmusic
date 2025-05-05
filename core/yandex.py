from yandex_music import Client, Playlist  # Добавляем импорт Playlist
from tqdm import tqdm
from typing import List, Dict  # Добавляем Dict
from .track import Track
import sys
import time  # Добавляем импорт time
import traceback  # Добавляем импорт traceback


class YandexMusicExporter:
    def __init__(self, token: str):
        self.client = Client(token).init()

    def export_liked_tracks(self) -> List[Track]:
        liked_tracks = self.client.users_likes_tracks()
        tracks = []
        print(f"Found {len(liked_tracks)} liked tracks in Yandex Music.")
        with tqdm(total=len(liked_tracks), desc='Fetching track details from Yandex') as pbar:
            for i, track in enumerate(liked_tracks):
                try:
                    # Пытаемся получить полную информацию о треке
                    full_track = track.fetch_track()
                    if full_track and full_track.artists:
                        artist_name = ', '.join([artist.name for artist in full_track.artists if artist.name])
                        track_name = full_track.title
                        if artist_name and track_name:
                            tracks.append(Track(artist=artist_name, name=track_name))
                        else:
                            pbar.write(f"Warning: Skipping track {i+1} due to missing artist or title after fetch.")
                    else:
                        pbar.write(f"Warning: Skipping track {i+1} due to empty details after fetch.")
                except TypeError as e:
                    # Ловим конкретную ошибку TypeError, связанную с отсутствием 'id'
                    if "'id'" in str(e):
                        pbar.write(f"Warning: Skipping track {i+1} due to missing artist ID from Yandex API. Error: {e}")
                    else:
                        # Если это другая ошибка TypeError, выводим ее и продолжаем
                        pbar.write(f"Warning: Skipping track {i+1} due to unexpected TypeError. Error: {e}")
                except Exception as e:
                    # Ловим другие возможные ошибки при получении трека
                    pbar.write(f"Warning: Skipping track {i+1} due to error fetching details. Error: {e}")
                finally:
                    pbar.update(1)  # Обновляем прогресс-бар в любом случае

        print(f"Successfully fetched details for {len(tracks)} tracks.")
        return tracks

    def export_playlists(self) -> Dict[str, List[Track]]:
        """Экспортирует только плейлист 'Распознано' и его треки."""
        target_playlist_name = "Понравилось на Радио" # <--- Указываем целевой плейлист
        print(f"Attempting to export only the playlist named '{target_playlist_name}'...")

        try:
            user_playlists = self.client.users_playlists_list()
            if not user_playlists:
                print("No playlists found for this user.")
                return {}
            print(f"Found {len(user_playlists)} total playlists. Searching for '{target_playlist_name}'...")
        except Exception as e:
            print(f"Error fetching playlists list: {e}")
            traceback.print_exc()
            return {}

        playlists_data: Dict[str, List[Track]] = {}
        # ---> Ищем только целевой плейлист <---
        playlist_short = next((p for p in user_playlists if p.title == target_playlist_name), None)

        if not playlist_short:
            print(f"Playlist '{target_playlist_name}' not found in user's playlists.")
            return {} # Возвращаем пустой словарь, если плейлист не найден

        # ---> Обрабатываем только найденный плейлист <---
        playlist_title = playlist_short.title
        print(f"\nProcessing playlist: '{playlist_title}' (Kind: {playlist_short.kind})")

        try:
            tracks_short_list = playlist_short.fetch_tracks()
            if not tracks_short_list:
                print(f"Playlist '{playlist_title}' is empty or track list could not be fetched.")
                playlists_data[playlist_title] = []
                return playlists_data # Возвращаем данные для этого плейлиста

            print(f"Fetching details for {len(tracks_short_list)} tracks in '{playlist_title}'...")
            tracks_in_playlist: List[Track] = []
            with tqdm(total=len(tracks_short_list), desc=f"Tracks in '{playlist_title}'", leave=False) as pbar:
                for track_short in tracks_short_list:
                    try:
                        full_track = track_short.fetch_track()
                        if full_track and full_track.artists:
                            artist_name = ', '.join([artist.name for artist in full_track.artists if artist.name])
                            track_name = full_track.title
                            if artist_name and track_name:
                                tracks_in_playlist.append(Track(artist=artist_name, name=track_name))
                            else:
                                pbar.write(f"Warning: Skipping track in '{playlist_title}' due to missing artist/title.")
                        elif full_track:
                            track_name = full_track.title
                            if track_name:
                                pbar.write(f"Info: Track '{track_name}' in '{playlist_title}' has no artists, skipping.")
                            else:
                                pbar.write(f"Warning: Skipping track in '{playlist_title}' due to missing title and artists.")
                        else:
                            pbar.write(f"Warning: Skipping track in '{playlist_title}' due to empty details from fetch_track().")
                    except TypeError as e:
                        if "'id'" in str(e):
                            pbar.write(f"Warning: Skipping track in '{playlist_title}' due to missing artist ID. Error: {e}")
                        else:
                            pbar.write(f"Warning: Skipping track in '{playlist_title}' due to unexpected TypeError. Error: {e}")
                    except Exception as e:
                        pbar.write(f"Warning: Skipping track in '{playlist_title}' due to error fetching details. Error: {e}")
                    finally:
                        pbar.update(1)
                        time.sleep(0.1)

            playlists_data[playlist_title] = tracks_in_playlist
            print(f"Successfully processed {len(tracks_short_list)} tracks for '{playlist_title}'. Found details for {len(tracks_in_playlist)} tracks.")

        except Exception as e:
            print(f"Error processing playlist '{playlist_title}' (failed to fetch track list?): {e}")
            traceback.print_exc()
            playlists_data[playlist_title] = {"error": f"Failed to process playlist (fetch_tracks error?): {e}"}

        # ---> Убираем цикл и задержку, так как обработали единственный плейлист <---

        return playlists_data
