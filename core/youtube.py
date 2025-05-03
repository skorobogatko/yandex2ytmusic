import os
import webbrowser
import time
import json
import urllib.parse
import traceback
from typing import List, Tuple, Optional
from tqdm import tqdm
from ytmusicapi import YTMusic, setup
from .track import Track


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
                    # --- НАЧАЛО ИЗМЕНЕНИЯ ---
                    # Убираем ручное кодирование URL
                    # query = urllib.parse.quote_plus(f'{track.artist} {track.name}')
                    query = f'{track.artist} {track.name}' # Передаем обычную строку
                    # --- КОНЕЦ ИЗМЕНЕНИЯ ---
                    # Логируем запрос
                    print(f"Отправляю запрос: {query}") # Теперь будет выводиться читаемый запрос
                    # Повторные попытки
                    for attempt in range(3):
                        try:
                            results = self.ytmusic.search(query)
                            break  # Если успешно, выходим из цикла повторных попыток
                        except json.JSONDecodeError as e:
                            # --- НАЧАЛО ИЗМЕНЕНИЯ ---
                            # Получаем последний ответ из сессии библиотеки
                            last_response = self.ytmusic._session.hooks['response'][-1] if self.ytmusic._session.hooks.get('response') else None
                            if last_response:
                                print(f"Ошибка JSON при попытке {attempt + 1}: {e}")
                                print(f"Статус код ответа: {last_response.status_code}")
                                print(f"Текст ответа: {last_response.text[:500]}...") # Выводим начало текста ответа
                            else:
                                print(f"Ошибка JSON при попытке {attempt + 1}, но не удалось получить ответ из сессии.")
                            # --- КОНЕЦ ИЗМЕНЕНИЯ ---
                            if attempt < 2:
                                time.sleep(5)  # Ждем перед следующей попыткой
                            else:
                                raise  # Если все попытки неудачны, выбрасываем исключение
                    else:
                        # Эта часть может быть недостижима, если все попытки вызвали JSONDecodeError
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
