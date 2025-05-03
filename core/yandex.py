from yandex_music import Client
from tqdm import tqdm
from typing import List
from .track import Track
import sys # Добавляем импорт sys


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
                    pbar.update(1) # Обновляем прогресс-бар в любом случае
        
        print(f"Successfully fetched details for {len(tracks)} tracks.")
        return tracks
