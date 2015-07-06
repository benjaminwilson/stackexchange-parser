# stackexchange-parser
A simple script for turning the StackExchange XML dumps into CSVs

Reads the Posts.xml and Comments.xml files from a StackExchange dump and
writes out three CSVs: + a CSV with columns ['id', 'title', 'text', 'url',
'creation_date'] containing information about each page (i.e. question
considered together with all its answers) + a CSV listing the documents ids
and the user ids pairs given by posts + the same, but for comments. All
outputs are UTF-8 encoded. Each row of the input file beginning with "<row" is
treated as an XML specification of a StackExchange post. Answers and Questions
are aggregated into a single output line by concatentating their texts. Posts
that are neither answers nor questions are ignored.

Usage example:

```
python stackexchange_parser.py --posts-input sample-inputs/Posts.xml --comments-input sample-inputs/Comments.xml --comments-output comments.csv --pages-output pages.csv --urlbase blah.com --posts-output posts.csv
```
