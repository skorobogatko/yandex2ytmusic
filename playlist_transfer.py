import argparse
import json
import os
import time
import traceback
from typing import Dict, List, Tuple

from tqdm import tqdm

from core.track import Track
from core import YandexMusicExporter
from core import YoutubeImoirter # Убедитесь, что имя класса правильное

# --- Новые или измененные функции/классы будут добавлены сюда ---

def parse_args() -> argparse.Namespace:
    """Парсит аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description='Transfer playlists from Yandex.Music to YouTube Music'
    )
    parser.add_argument(
        '--yandex', type=str, required=True, help='Yandex Music token'
    )
    parser.add_argument(
        '--output', type=str, default='playlist_transfer_report.json',
        help='Output json file for the transfer report'
    )
    parser.add_argument(
        '--youtube', type=str, default='youtube.json',
        help='Youtube Music credentials file. If file not exists, it will be created.'
    )
    # Убираем аргумент --cache, так как кеширование плейлистов пока не реализуем
    return parser.parse_args()

def transfer_playlists(
        yandex_exporter: YandexMusicExporter,
        youtube_importer: YoutubeImoirter,
        out_path: str
    ) -> None:
    """Основная функция для переноса плейлистов."""
    print('Exporting playlists from Yandex Music...')
    try:
        # Эта функция будет добавлена в YandexMusicExporter
        playlists_data = yandex_exporter.export_playlists()
        if not playlists_data:
            print("No playlists found or exported from Yandex Music.")
            return
        print(f"Exported {len(playlists_data)} playlists from Yandex Music.")
    except Exception as e:
        print(f"Error exporting playlists from Yandex Music: {e}")
        traceback.print_exc()
        return

    print('Importing playlists to YouTube Music...')
    try:
        # Эта функция будет добавлена в YoutubeImporter
        import_results = youtube_importer.import_playlists(playlists_data)
    except Exception as e:
        print(f"Error importing playlists to YouTube Music: {e}")
        traceback.print_exc()
        import_results = {"error": str(e)} # Сохраняем информацию об общей ошибке

    print('Transfer process finished. Saving report...')
    # Сохраняем отчет о переносе
    try:
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(import_results, f, ensure_ascii=False, indent=4)
        print(f"Report saved to {out_path}")
    except Exception as e:
        print(f"Error saving report to {out_path}: {e}")

def main() -> None:
    """Главная функция скрипта."""
    args = parse_args()

    try:
        yandex_exporter = YandexMusicExporter(args.yandex)
    except Exception as e:
        print(f"Error initializing Yandex Music exporter: {e}")
        return

    try:
        # Убедитесь, что имя класса YoutubeImporter правильное
        youtube_importer = YoutubeImoirter(args.youtube)
    except Exception as e:
        print(f"Error initializing YouTube Music importer: {e}")
        return

    transfer_playlists(yandex_exporter, youtube_importer, args.output)

if __name__ == '__main__':
    main()