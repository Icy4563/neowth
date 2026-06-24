import csv
from typing import List, Tuple, Union, Dict, Any

CSV_FILE = 'worldcities.csv'

_cities: List[Dict[str, Any]] = []


def _load_data():
    global _cities
    if _cities:
        return
    try:
        with open(CSV_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row['lat'] = float(row['lat'])
                row['lng'] = float(row['lng'])
                try:
                    row['population'] = int(float(row['population'])) if row['population'] else 0
                except ValueError:
                    row['population'] = 0
                _cities.append(row)
    except FileNotFoundError:
        raise FileNotFoundError(f"CSV file '{CSV_FILE}' not found.")




def find_city(city_name: str, partial: bool = False, show_id: bool = True) -> Tuple[List[dict], List[str]]:
    """
    Search for a city by name.
    If partial=True, matches substrings (case-insensitive).

    Returns a tuple:
        (list_of_match_dicts, list_of_ids)
    Sorted by population (descending).
    """
    _load_data()

    name = city_name.lower()

    if partial:
        matches = [city for city in _cities if name in city['city'].lower()]
    else:
        matches = [city for city in _cities if city['city'].lower() == name]

    matches.sort(key=lambda x: x['population'], reverse=True)

    ids = [city['id'] for city in matches]

    if show_id:
        return matches, ids
    elif not show_id:
        return matches



def get_coordinates(city_name: str, partial: bool = False) -> Union[
    Tuple[str, str, str, float, float],
    List[Tuple[str, str, str, float, float]]
]:
    """
    Returns (city, admin_name, country, lat, lng).
    If one match -> returns a tuple.
    If multiple -> returns list of tuples.
    """
    results, _ = find_city(city_name, partial=partial)

    coords = [(r['city'], r['admin_name'], r['country'], r['lat'], r['lng'])
              for r in results]

    if len(coords) == 1:
        return coords[0]
    
    if type(coords) is list:
        coords = coords[0]
        return_object = coords[3], coords[4]

    else:
        return_object = coords[3], coords[4]
    
    # return_object = coords if type(coords) is list else coords[3], coords[4]

    return return_object 

def get_city_by_id(city_id: str) -> Union[Tuple, None]:
    """
    Returns a tuple of city data for the row with matching ID.
    Returns None if not found.

    Tuple format:
        (city, city_ascii, lat, lng, country,
         iso2, iso3, admin_name, capital, population, id)
    """
    _load_data()

    for city in _cities:
        if city['id'] == city_id:
            return (
                city['city'],
                city['city_ascii'],
                city['lat'],
                city['lng'],
                city['country'],
                city['iso2'],
                city['iso3'],
                city['admin_name'],
                city['capital'],
                city['population'],
                city['id']
            )

    return None
