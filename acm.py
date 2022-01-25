import os
import re
import spacy
import logging
from tqdm import tqdm


def setup_required(func):
    """Decorator to ensure respository is setup before being used."""
    def wrapper_setup_required(self, *args, **kwargs):
        if not self.__setup_flag__:
            logging.error('Repository setup required to use {}. Did you \
                forget to run acmRepository.setup()?'.format(func.__name__))
        else:
            return func(*args, **kwargs)
        return wrapper_setup_required

class ACMRepo:
    """This class keeps track of the .bib files with bibliography items
        exported from the ACM Digital Library.
    """

    """
    Parameters
    ----------
    repo_dir : str
        The directory with the list of .bib files.
    """
    def __init__(self, repo_dir, with_abstract_nlp=False):
        self.repo_dir = repo_dir
        self.bibs = {}
        self.length = None
        self.key_set = set()
        self.with_keywords = []
        self.__setup_flag__ = False
        self.with_abstracts = []
        self.with_abstracts_nlp = with_abstract_nlp
        if with_abstract_nlp:
            self.nlp = spacy.load('en_core_web_sm')

    @setup_required
    def set_difference(self, acm_repo):
        """Computes the set of documents which are exclusive to this repo."""

        """
        Paramaters
        ----------
        acm_repo : ACMRepo
            An initialized ACM repositotry object.

        Returns
        -------
        set
            A set of doi that do not exist in acm_repo
        """
        return self.key_set.difference(acm_repo.key_set)

    # @setup_required
    def difference(self, acm_repo):
        diff_set = self.key_set.difference(acm_repo.key_set)
        diff_repo = ACMRepo(self.repo_dir)
        diff_repo.key_set = diff_set
        for k in diff_set:
            diff_repo.bibs[k] = self.bibs[k]
            if k in self.with_keywords: diff_repo.with_keywords.append(k)
            if k in self.with_abstracts: diff_repo.with_abstracts.append(k)
        diff_repo.length = len(diff_repo.bibs.keys())
        if self.with_abstracts_nlp:
            diff_repo.nlp = self.nlp
        
        diff_repo.setup_flag = True

        return diff_repo

    def setup(self, force=False):
        if self.__setup_flag__ and not force:
            logging.warning('There is already a repository set up. \
                Use force=True to force reinitialization.')
        else:
            logging.info('==========Setting up repository for {}========='\
                .format(self.repo_dir))
            self.__extract_bibs__()
            self.key_set = set(self.bibs.keys())

            self.length = len(self.bibs)
            self.__extract_keywords__()
            self.__convert_date__()

            if self.with_abstracts_nlp:
                self.__build_abstract_nl_tree__()

            self.setup_flag = True
            logging.info('=========Repository Setup Done==========')

        return self
    
    def __extract_bibs__(self):
        logging.info('Extracting bibliography items.')
        for file_ in tqdm(os.listdir(self.repo_dir),\
            bar_format='{l_bar}{bar:10}{r_bar}{bar:-10b}'):
            self.bibs.update(self.get_bib_items_from_file(\
                os.path.join(self.repo_dir, file_)))

    def __extract_keywords__(self):
        logging.info('Extracting Keywords.')
        for k, v in tqdm(self.bibs.items()):
            if 'keywords' in v.keys():
                v['keywords'] = v['keywords'].split(', ')
                self.with_keywords.append(k)
        logging.info('Total documents with keywords: {}'\
            .format(len(self.with_keywords)))

    def __convert_date__(self):
        logging.info('Converting Year to Integer.')
        for k, v in tqdm(self.bibs.items()):
            if 'year' in v.keys():
                v['year'] = int(v['year'])

    def __build_abstract_nl_tree__(self):
        logging.info('Building Natural Language Tree for abstracts.')
        for k, v in tqdm(self.bibs.items()):
            if 'abstract' in v.keys():
                v['abstract_nl_tree'] = self.nlp(v['abstract'])
                self.with_abstracts.append(k)
        logging.info('Total documents with abstracts: {}'\
            .format(len(self.with_abstracts)))

    def __tokenize__(self, text_):
        # TODO
        pass

    def update_bibs(self, file_path):
        self.bibs.update(self.get_bib_items_from_file(file_path))
        # TODO update keywords and abstrac extraction

    def remove_bib(self, doi_key):
        if doi_key in self.bibs.keys():
            del self.bibs[doi_key]
            self.length = len(self.bibs)
        if doi_key in self.with_keywords:
            self.with_keywords.remove(doi_key)
        if doi_key in self.with_abstracts:
            self.with_abstracts.remove(doi_key)

    def export_bib_file(self, file_path):
        with open(file_path, 'w') as f:
            for key, val in self.bibs.items():
                raw_biblst = val['raw'].split('\n')
                t_lines = len(raw_biblst)
                f.write(raw_biblst[0])
                for line in raw_biblst[1:t_lines-1]:
                    f.write('\n\t')
                    f.write(line)
                f.write('\n')
                f.write(raw_biblst[t_lines-1])
                
                f.write('\n\n')

    def batch_remove_bibs(self, doi_key_lst):
        for doi_key in doi_key_lst:
            self.remove_bib(doi_key)


    @staticmethod
    def get_bib_items_from_file(file_path):

        type_regex = r'@\w+'
        id_regex = r'(?<={)(?:[^}])*?(?=,\n)'
        group_vals = r'{(?:[^{}]*|{[^{}]*})*}'
        group_keys = r'(?<=).{3,15}?(?= = {)'

        bib_dict = {}
        bib_str = ''
        with open(file_path, 'r') as f:
            for line in f:
                bib_str += line
                # debug_str += line
                if line[0] == ('}'):
                    item_dict = {}
                    item_dict['raw'] = bib_str.strip()

                    bib_type = re.match(type_regex, item_dict['raw'])\
                        .group(0)[1:]
                    bib_id = re.search(id_regex, item_dict['raw'])\
                        .group(0)[:-1]

                    trunc_str = bib_str[len(bib_type)+len(bib_id)+5:]
                    
                    bib_keys = re.findall(group_keys, trunc_str)
                    bib_vals = re.findall(group_vals, trunc_str)

                    item_dict['type'] = bib_type
                    item_dict.update({k:v.strip()[1:-1] for (k, v) in \
                        zip(bib_keys, bib_vals)})
                    bib_dict[bib_id] = item_dict
                if line[0] == '\n':
                    bib_str = ''

        return bib_dict
