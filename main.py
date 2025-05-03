import argparse
import json
import os

from core.track import Track
from core import YandexMusicExporter
from core import YoutubeImoirter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Transfer tracks from Yandex.Music to YouTube Music'
    )
    parser.add_argument(
        '--yandex', type=str, help='Yandex Music token'
    )
    parser.add_argument(
        '--output', type=str, default='tracks.json', help='Output json file'
    )
    parser.add_argument(
        '--youtube', type=str, default='youtube.json', 
        help='Youtube Music credentials file. If file not exists, it will be created.'
    )
    parser.add_argument(
        '--cache', type=str, default='yandex_tracks.json', 
        help='Cache file for Yandex Music tracks.'
    )
    return parser.parse_args()


def load_tracks_from_cache(cache_path: str) -> list:
    """Loads tracks from a JSON cache file."""
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_tracks_to_cache(cache_path: str, tracks: list) -> None:
    """Saves tracks to a JSON cache file."""
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(
            [{'artist': track.artist, 'name': track.name} for track in tracks], 
            f, 
            ensure_ascii=False, 
            indent=4
        )


def move_tracks(
        importer: YandexMusicExporter, exporter: YoutubeImoirter, 
        out_path: str, cache_path: str
    ) -> None:
    data = {
        'liked_tracks': [],
        'not_found': [],
        'errors': [],
    }
    
    # Try loading tracks from cache
    print(f'Checking for cached tracks at {cache_path}...')
    cached_tracks = load_tracks_from_cache(cache_path)
    
    if cached_tracks:
        print('Using cached tracks from Yandex Music.')
        tracks = [Track(track['artist'], track['name']) for track in cached_tracks]
    else:
        print('Exporting liked tracks from Yandex Music...')
        tracks = importer.export_liked_tracks()
        save_tracks_to_cache(cache_path, tracks)  # Save tracks to cache
    
    tracks.reverse()

    for track in tracks:
        data['liked_tracks'].append({
            'artist': track.artist,
            'name': track.name
        })

    print('Importing liked tracks to Youtube Music...')
    not_found, errors = exporter.import_liked_tracks(tracks)

    for track in not_found:
        data['not_found'].append({
            'artist': track.artist,
            'name': track.name
        })
        print(f'{track.artist} - {track.name}')
    
    for track in errors:
        data['errors'].append({
            'artist': track.artist,
            'name': track.name
        })
    
    print(f'{len(not_found)} not found tracks, {len(errors)} errors.')

    str_data = json.dumps(data, ensure_ascii=False, indent=4)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(str_data)


def main() -> None:
    args = parse_args()
    importer = YandexMusicExporter(args.yandex)
    exporter = YoutubeImoirter(args.youtube)
    move_tracks(importer, exporter, args.output, args.cache)


if __name__ == '__main__':
    main()