#!/usr/bin/env python

# This file is part of Living Labs Challenge, see http://living-labs.net.
#
# Living Labs Challenge is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Living Labs Challenge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Living Labs Challenge. If not, see <http://www.gnu.org/licenses/>.

import base64
import hashlib
import xml.etree.ElementTree as et
import argparse
import requests
import json
import random
import time

HOST = "http://127.0.0.1:5000/api"
PCLICK = {0: 0.05,
          1: 0.5,
          2: 0.95}
PSTOP = {0: 0.2,
         1: 0.5,
         2: 0.9}

QUERYENDPOINT = "site/query"
DOCENDPOINT = "site/doc"
DOCLISTENDPOINT = "site/doclist"
RANKIGNENDPOINT = "site/ranking"
FEEDBACKENDPOINT = "site/feedback"

HEADERS = {'content-type': 'application/json'}


def store_queries(key, query_file):
    tree = et.parse(query_file)
    topics = tree.getroot()
    queries = {"queries": []}
    for topic in topics.iter("topic"):
        qid = topic.attrib["number"]
        query = topic.find("query")
        qstr = query.text
        queries["queries"].append({
            "qstr": qstr,
            "site_qid": hashlib.sha1(qid).hexdigest(),
        })
    url = "/".join([HOST, QUERYENDPOINT, key])
    requests.put(url, data=json.dumps(queries), headers=HEADERS)


def store_doc(key, doc, site_docid):
    title = "Dummy Title " + str(site_docid)
    content = "Dummy Content " + str(site_docid)
    doc = {
        "site_docid": site_docid,
        "title": title,
        "content": base64.b64encode(content),
        "content_encoding": "base64",
        }
    url = "/".join([HOST, DOCENDPOINT, key, site_docid])
    requests.put(url, data=json.dumps(doc), headers=HEADERS)


def store_doclist(key, run_file):
    def put_doclist(doclist, current_qid):
        site_qid = hashlib.sha1(current_qid).hexdigest()
        doclist["site_qid"] = site_qid
        url = "/".join([HOST, DOCLISTENDPOINT, key, site_qid])
        requests.put(url, data=json.dumps(doclist), headers=HEADERS)

    doclist = {"doclist": []}
    current_qid = None
    for line in open(run_file, "r"):
        qid, _, docid, _, _, _ = line.split()
        if current_qid != None and current_qid != qid:
            put_doclist(doclist, current_qid)
            doclist = {"doclist": []}
        site_docid = hashlib.sha1(docid).hexdigest()
        store_doc(key, docid, site_docid)
        doclist["doclist"].append({"site_docid": site_docid})
        current_qid = qid
    put_doclist(doclist, current_qid)


def get_ranking(key, qid):
    site_qid = hashlib.sha1(qid).hexdigest()
    url = "/".join([HOST, RANKIGNENDPOINT, key, site_qid])
    r = requests.get(url, headers=HEADERS)
    print r.json()
    r.raise_for_status()
    json = r.json()
    return json["sid"], json["doclist"]


def store_feedback(key, qid, sid, ranking, clicks):
    site_qid = hashlib.sha1(qid).hexdigest()
    doclist = {"sid": sid,
               "site_qid": site_qid,
               "type": "clicks",
               "doclist": []}
    for docid, click in zip(ranking, clicks):
        site_docid = hashlib.sha1(docid).hexdigest()
        doclist["doclist"].append({"site_docid": site_docid})
        if click:
            doclist["doclist"][-1]["clicked"] = True

    url = "/".join([HOST, FEEDBACKENDPOINT, key, sid])
    r = requests.put(url, data=json.dumps(doclist), headers=HEADERS)
    print r.json()
    r.raise_for_status()


def get_labels(qrel_file):
    labels = {}
    for line in open(qrel_file, "r"):
        qid, _, docid, label = line.split()
        if not qid in labels:
            labels[qid] = {}
        labels[qid][docid] = int(label)
    return labels


def get_clicks(ranking, labels):
    clicks = [0] * len(ranking)
    for docid in ranking:
        label = labels[docid]
        rand = random.random()
        if rand < PCLICK[label]:
            clicks[pos] = 1
            rand = random.random()
            if rand < PSTOP[label]:
                break
    return clicks


def simulate_clicks(key, qrel_file):
    labels = get_labels(qrel_file)
    while True:
        qid = random.choice(labels.keys())
        sid, ranking = get_ranking(key, qid)
        #TODO: once in a while, drop a document before showing it to the user.
        clicks = get_clicks(ranking, labels[qid])
        store_feedback(key, qid, sid, ranking, clicks)
        time.sleep(random.random())

if __name__ == '__main__':
    description = "Living Labs Challenge's API Server"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-k', '--key', type=str, required=True,
                        help='Provide a user key.')
    parser.add_argument('-q', '--store_queries', action="store_true",
                        default=False,
                        help='Store some queries (needs --query_file).')
    parser.add_argument('--query_file', default="../data/queries.xml",
                        help='Path to TREC style query file '
                        '(default: %(default)s).')
    parser.add_argument('-d', '--store_doclist', action="store_true",
                        default=False,
                        help='Store a document list (needs --run_file)')
    parser.add_argument('--run_file', default="../data/run.txt",
                        help='Path to TREC style run file '
                        '(default: %(default)s).')
    parser.add_argument('-s', '--simulate_clicks', action="store_true",
                        default=False,
                        help='Simulate clicks (needs --qrel_file).')
    parser.add_argument('--qrel_file', default="../data/qrel.txt",
                        help='Path to TREC style qrel file '
                        '(default: %(default)s).')
    args = parser.parse_args()
    if args.store_queries:
        store_queries(args.key, args.query_file)
    if args.store_doclist:
        store_doclist(args.key, args.run_file)
    if args.simulate_clicks:
        simulate_clicks(args.key, args.qrel_file)
