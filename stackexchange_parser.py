import csv, sys, json, argparse
import logging

from bs4 import BeautifulSoup
from collections import defaultdict
from xml_utils import lazy_xml_chunks

PAGE_COLS = ['id', 'title', 'text', 'url', 'creation_date']


def strip_newlines(unicodetext):
    # replace linefeeds with spaces
    return ' '.join(unicodetext.splitlines())

def encode(obj):
    if isinstance(obj, unicode):
        return obj.encode('utf-8', 'ignore')
    return obj

def utf8_encode_dict(inputdict):
    return {encode(key): encode(value) for key, value in inputdict.iteritems()}

def post_html_to_text(html, strip_tags=[]):
    bshtml = BeautifulSoup(html)
    for tag in strip_tags:
        for res in bshtml.find_all(tag):
            res.decompose()
    return strip_newlines(bshtml.text)


class AggregatedPost:
    """
    An aggregation of a Stack Exchange question, answers and comments.
    """

    def __init__(self, source):
        """
        source is e.g. judaism.stackexchange.com and is used to build the URL
        for the question.
        """
        self.source = source
        self.title = ''
        self.texts = []
        self.meta = {}
        self.posting_users = []
        self.commenting_users = []

    def append_question(self, question_bs):
        """
        append the question beautifulsoup object given the to current aggregate.
        assumes that the 'Id' field of a question matches the 'ParentId' field of any answer in the same aggregate.
        """
        self.external_id = question_bs['Id']
        self.title = question_bs['Title']
        self.tags = question_bs['Tags']
        self.texts.append(question_bs['Body'])
        self.creation_date = question_bs['CreationDate'][:10]
        try:
            self.posting_users.append(question_bs['OwnerUserId']) # present only if user has not been deleted
        except KeyError:
            pass

    def append_answer(self, answer_bs):
        """
        append the answer beautifulsoup object given the to current aggregate.
        assumes that the 'Id' field of a question matches the 'ParentId' field of any answer in the same aggregate.
        """
        self.external_id = answer_bs['ParentId']
        self.texts.append(answer_bs['Body'])
        try:
            self.posting_users.append(answer_bs['OwnerUserId']) # present only if user has not been deleted
        except KeyError:
            pass

    def append_comment(self, comment_bs):
        """
        Assuming that the beautifulsoup object given is of a comment associated
        with a post for this aggregate post, extract the user id of the
        commenting user.
        Text of the comment is ignored (it is typically not meaningful).
        """
        try:
            self.commenting_users.append(comment_bs['UserId']) # present only if user has not been deleted
        except KeyError:
            pass

    def to_document_row(self, strip_tags=[]):
        """
        return dictionary with keys PAGE_COLS.  Values are unicode.
        """
        url = 'http://' + self.source + '/questions/' + self.external_id
        text_as_html = u' '.join(self.texts)
        text = post_html_to_text(text_as_html)
        return dict(zip(PAGE_COLS, [self.external_id, self.title, text, url, self.creation_date]))

HELP_STR = """
Reads the Posts.xml and Comments.xml files from a StackExchange dump
and writes out three CSVs:
+ a CSV with columns %s containing information about each page (i.e. question
considered together with all its answers)
+ a CSV listing the documents ids and the user ids pairs given by posts
+ the same, but for comments.

All outputs are UTF-8 encoded.

Each row of the input file beginning with "<row" is treated as an XML
specification of a StackExchange post.  Answers and Questions are aggregated
into a single output line by concatentating their texts.  Posts that are
neither answers nor questions are ignored.
""" % PAGE_COLS

QUESTION = "1"
ANSWER = "2"

def parse_xml_rows(xml_file, parsing_fn, logger): # parsing_fn accepts BeautifulSoup objects representing a single row of the XML file
    with open(xml_file) as f:
        for row_xml in f:
            row_xml = row_xml.strip()
            if row_xml.startswith('<row'):
                try:
                    row = BeautifulSoup(row_xml, 'xml', from_encoding='utf-8').row
                    parsing_fn(row)
                except Exception as e:
                    logger.error('skipped xml row: %s error: %s' % (row_xml, str(e)))

def write_user_item_pairs(filename, pairs):
    with file(filename, 'w') as f:
        for item_id, user_id in pairs:
            f.write('%s,%s\n' % (item_id, user_id))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=HELP_STR)
    parser.add_argument('--posts-input', help='XML input file of the posts', required=True)
    parser.add_argument('--comments-input', help='XML input file of the comments', required=True)
    parser.add_argument('--posts-output', help='CSV output file of the posts with columns user id and question id', required=True)
    parser.add_argument('--comments-output', help='CSV output file of the comments with columns user id and question id', required=True)
    parser.add_argument('--pages-output', help='CSV output file of the pages with columns %s' % ','.join(PAGE_COLS), required=True)
    parser.add_argument('--urlbase', help='base URL, e.g. english.stackexchange.com', required=True)
    parser.add_argument('--strip-tags', help='tag types to strip from posts', nargs='*', default=[])
    args = parser.parse_args()
    agg_posts = defaultdict(lambda: AggregatedPost(args.urlbase))
    post_id_to_agg_post = {}

    def parse_posts_row(row):
        if row['PostTypeId'] == QUESTION:
            agg_post = agg_posts[row['Id']]
            agg_post.append_question(row)
            post_id_to_agg_post[row['Id']] = agg_post
        elif row['PostTypeId'] == ANSWER:
            agg_post = agg_posts[row['ParentId']]
            agg_post.append_answer(row)
            post_id_to_agg_post[row['Id']] = agg_post

    def parse_comments_row(row):
        agg_post = post_id_to_agg_post[row['PostId']]
        agg_post.append_comment(row)

    parse_xml_rows(args.posts_input, parse_posts_row, logger=logging)
    parse_xml_rows(args.comments_input, parse_comments_row, logger=logging)

    # write out the CSV of page information
    with file(args.pages_output, 'w') as f:
        writer = csv.DictWriter(f, PAGE_COLS, delimiter=",")
        for agg_post in agg_posts.values():
            row_enc = utf8_encode_dict(agg_post.to_document_row(strip_tags=args.strip_tags))
            writer.writerow(row_enc)
    # write out the collaborative CSVs with columns document id, user id
    post_pairs = [(agg_post.external_id, user_id) for agg_post in agg_posts.values() for user_id in agg_post.posting_users]
    comment_pairs = [(agg_post.external_id, user_id) for agg_post in agg_posts.values() for user_id in agg_post.commenting_users]
    write_user_item_pairs(args.posts_output, post_pairs)
    write_user_item_pairs(args.comments_output, comment_pairs)
