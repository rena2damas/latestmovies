import services.movie_service as ms
from models.movie import Movie
from models.schedule import Schedule
from bson.json_util import dumps
import json
import sys
from PIL import Image
import urllib.request, io
import services.google_vision as im
from configs.config import CONFIG

ELECTED_CANDIDATE_SCORE = 5


def _print_img(uri):
    """Printing image"""
    file = io.BytesIO(urllib.request.urlopen(uri).read())
    image = Image.open(file)
    image.show()
    im.detect_web_uri(uri)


if __name__ == '__main__':
    unresolved_movies_json = json.loads(dumps(ms.get_all_unresolved_movies()))

    # Solving each unresolved movie
    for unresolved_movie_json in unresolved_movies_json:
        unresolved_movie = Movie(unresolved_movie_json)  # Getting object from json

        schedule = Schedule(json.loads(dumps(ms.get_channel_movie(unresolved_movie.sapo_id))))

        print('\n')
        print('*** {} *** [{}]'.format(unresolved_movie.sapo_id, schedule.sapo_channel))
        print('Movie sapo title: {}'.format(unresolved_movie.sapo_title))
        print('Movie sapo description: {}'.format(unresolved_movie.sapo_description))
        print('* Choose one of the following candidates *')

        img_uri = CONFIG.SAPO_IMAGE.format(unresolved_movie.sapo_id)
        _print_img(img_uri)  # Printing movie image
        success_google_vision, annotations = im.detect_web_uri(img_uri)  # Getting nnotation from Google Vision API

        # Electing the right candidate
        candidates_json = json.loads(dumps(ms.get_all_candidates(unresolved_movie.sapo_id)))
        candidates = []

        ###############################################
        # Evaluating each candidate to a set of rules #
        ###############################################
        for candidate_json in candidates_json:
            candidate = Movie(candidate_json)  # Getting object from json
            rules = im.evaluate_candidate(annotations, candidate) if success_google_vision else []
            rules += candidate.evaluate_candidate_title()
            rules += candidate.evaluate_candidate_description()
            candidate.set_score(rules, unresolved_movie)  # Setting score based on a set of rules/parameters
            candidates.append((candidate, rules))

        candidates.sort(key=lambda tuple: tuple[0].score, reverse=True)  # Sorting by number of matches

        for index, (candidate, matches) in enumerate(candidates, start=1):
            print('\n')
            print('[{}] Title: {} - {}'.format(index, candidate.imdb_title, candidate.imdb_id))
            print('    OMDB Description: {}'.format(candidate.plot))
            print('    IMDb Description: {}'.format(candidate.imdb_description))
            print('    Actors: {}'.format(candidate.actors))
            print('    Scored: {} *** {} matches: {}'.format(candidate.score, len(matches), matches))

        # Additional candidates to include in movie selection
        has_additional_candidates = False
        if success_google_vision:
            additional_candidates = im.google_vision_candidates(annotations, [tuple[0] for tuple in candidates])
            if len(additional_candidates) > 0:
                print('\n')
                print('Additional candidates found')
                has_additional_candidates = True
                for additional_candidate in additional_candidates:
                    print(additional_candidate)

        # If score difference between 1st and 2nd candidate is > 5, elect candidate
        if len(candidates) > 0 and \
                ((len(candidates) == 1 and candidates[0][0].score > ELECTED_CANDIDATE_SCORE) or
                 (len(candidates) > 1 and candidates[0][0].score - candidates[1][0].score > ELECTED_CANDIDATE_SCORE)):
            elected = candidates[0][0]
            score_difference = elected.score if len(candidates) == 1 else elected.score - candidates[1][0].score
            print('\n')
            print('***')
            print('Movie \'{}\' automatically elected with score of {} and difference of {}'
                  .format(elected.imdb_title, elected.score, score_difference))
            print('***')
            elected.isresolved = True
            ms.replace_movie(elected)  # Replace movie with elected one
            ms.delete_candidates(unresolved_movie.sapo_id)  # Deleting all previous candidates

        # Otherwise, manually election
        else:
            print('Chosen option: ')
            option = sys.stdin.readline()  # reading option from stdin

            try:  # Check whether the input is an int
                option = int(option)
            except ValueError:
                if option[:2] == 'tt':  # Checking whether it is an IMDb ID
                    unresolved_movie.imdb_id = option.replace('\n', '')
                    ms.complete_movie_with_omdb(unresolved_movie)
                    unresolved_movie.imdb_title = unresolved_movie.title + ' (' + unresolved_movie.year + ')'
                    unresolved_movie.isresolved = True
                    ms.replace_movie(unresolved_movie)  # Replace old entry with updated one
                    ms.delete_candidates(unresolved_movie.sapo_id)  # Delete candidates
                else:
                    raise Exception('Invalid option')
            else:
                elected = candidates[option - 1][0]
                elected.isresolved = True
                ms.replace_movie(elected)  # Replace movie with elected one
                ms.delete_candidates(unresolved_movie.sapo_id)  # Deleting all previous candidates
