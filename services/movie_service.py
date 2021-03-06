import json
import urllib, urllib.request
from configs.config import CONFIG, db
from models.movie import Movie
import re


def get_candidates(movie):
    """Getting movie candidates from Google search"""
    query = movie.sapo_title + ' imdb'
    params = {
        'key': CONFIG.GOOGLE_KEY,
        'cx': CONFIG.GOOGLE_CX,
        'q': query
    }
    url = CONFIG.GOOGLE_ENDPOINT + '?' + urllib.parse.urlencode(params)
    print(url)
    response = json.loads(urllib.request.urlopen(url).read().decode('utf-8'))

    candidates = []

    for item in response['items']:
        if 'pagemap' in item and 'displayLink' in item and 'metatags' in item['pagemap'] and \
                item['displayLink'] == 'www.imdb.com':
            for metatag in item['pagemap']['metatags']:
                if 'og:site_name' in metatag and metatag['og:site_name'] == 'IMDb' and \
                        'og:title' in metatag and \
                        '(TV Series' not in metatag['og:title'] and \
                        '(Video Game' not in metatag['og:title'] and \
                        'Official Trailer' not in metatag['og:title'] and \
                        'pageid' in metatag and not any(c.imdb_id == metatag['pageid'] for c in candidates):

                    candidate = Movie()
                    candidate.sapo_id = movie.sapo_id
                    candidate.sapo_title = movie.sapo_title
                    candidate.sapo_description = movie.sapo_description
                    candidate.imdb_id = metatag['pageid']
                    candidate.imdb_title = metatag['og:title']
                    candidate.imdb_description = metatag['og:description']

                    if complete_movie_with_omdb(candidate):  # Adding further attributes to the movie object
                        candidates.append(candidate)

    return candidates


def complete_movie_with_omdb(movie):
    """Fill all relevant info of a movie"""
    params = {
        'apikey': CONFIG.OMDB_KEY,
        'i': movie.imdb_id
    }
    url = CONFIG.OMDB_ENDPOINT + '?' + urllib.parse.urlencode(params)
    print(url)

    response = json.loads(urllib.request.urlopen(url).read().decode('utf-8'))

    if response['Response'] == 'False':
        return False

    movie.title = response['Title']
    movie.year = response['Year']
    movie.rated = response['Rated']
    movie.released = response['Released']
    movie.duration = response['Runtime']
    movie.genre = response['Genre']
    movie.director = response['Director']
    movie.writer = response['Writer']
    movie.actors = response['Actors']
    movie.plot = response['Plot']
    movie.language = response['Language']
    movie.country = response['Country']
    movie.awards = response['Awards']
    movie.poster = response['Poster']
    movie.rating_imdb = response['imdbRating']
    movie.rating_rotten_tomatoes = \
        next((rating for rating in response['Ratings'] if rating['Source'] == 'Rotten Tomatoes'), {'Value': ''})[
            'Value']
    movie.rating_metacritic = response['Metascore']
    movie.website = response['Website'] if 'Website' in response else ''

    return True


def get_movie_in_db_by_id(sapo_id):
    """Gets movie from database given its ID"""
    return db.movie.find_one({'sapo_id': sapo_id})


def save_movie(movie):
    """Save movie into database"""
    db.movie.insert(movie.to_dict())


def replace_movie(movie):
    """Replacing movie entry with the new one"""
    db.movie.delete_one({'sapo_id': movie.sapo_id})
    if hasattr(movie, '_id'): delattr(movie, '_id')
    save_movie(movie)


def save_schedule(schedule):
    """Save schedule into database"""
    db.schedule.insert(schedule.to_dict())


def exists_movie_in_db_by_sapo_id(sapo_id):
    """Check whether a movie already exists in database by ID"""
    return db.movie.find({'sapo_id': sapo_id}).count() != 0


def get_movie_in_db_by_title(sapo_title):
    """Gets a movie in db given its title"""
    return db.movie.find({'sapo_title': re.compile(sapo_title
                                                   .replace('(', '\(')
                                                   .replace(')', '\)')
                                                   .replace('$', '\$'), re.IGNORECASE)})


def get_movie_alias_by_id(sapo_id):
    """Gets a movie alias given an id"""
    return db.movie.find_one({'alias_ids': {'$in': [sapo_id]}})


def get_movie_alias_by_title(sapo_title):
    """Gets a movie alias given a title"""
    return db.movie.find({'alias_titles': {'$in': [sapo_title]}})


def get_alias_movie_by_aliasof(sapo_id):
    """Gets the alias of movie given its alias id"""
    return db.movie_aliases.find({'alias_of': sapo_id})


def exists_schedule_in_db(sapo_id, sapo_channel, sapo_start_datetime):
    """Check whether a schedule already exists in database"""
    return db.schedule.find({
        'sapo_id': sapo_id,
        'sapo_channel': sapo_channel,
        'sapo_start_datetime': sapo_start_datetime
    }).count() != 0


def save_candidates(candidates):
    """Add movie to the unresolved movies in the database"""
    for candidate in candidates:
        db.candidate.insert(candidate.to_dict())  # Store unresolved entry in database


def delete_candidates(sapo_id):
    """Delete candidate movies"""
    db.candidate.delete_many({'sapo_id': sapo_id})


def get_all_unresolved_movies():
    """Get list of unresolved movies"""
    return db.movie.find({'isresolved': False})


def get_all_candidates(sapo_id):
    """Getting list of unresolved movies"""
    return db.candidate.find({'sapo_id': sapo_id})


def get_channel_movie(sapo_id):
    """Getting first channel found of a certain movie"""
    return db.schedule.find_one({'sapo_id': sapo_id})
