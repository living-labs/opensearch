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

import os
import time
import rollbar
import rollbar.contrib.flask
import atexit
import datetime
from flask import Flask, g, redirect
from flask.ext.restful import Api, abort
from flask_limiter import Limiter
from flask import got_request_exception
from apscheduler.schedulers.background import BackgroundScheduler

from .. import core
from apiutils import ApiResource, ContentField

from ll.core.db import db
from ll.core.config import config
from ll.core.user import send_email, get_user

import pickle

def db_cleanup_old():
    print "Database cleanup task started"
    age_threshold = datetime.datetime.now() - datetime.timedelta(days=config["RUN_AGE_THRESHOLD_DAYS"])
    reactivation_period = datetime.timedelta(days=config["REACTIVATION_PERIOD_DAYS"])


    # Get list of all queries
    q = {"deleted": {"$ne": True}}
    queries = [query for query in db.query.find(q)]

    for query in queries:
        allruns = query["runs"].items()
        for userid, runid_pair in allruns:
            # Check if runid is paired with a timestamp (new format)
            if isinstance(runid_pair, list):
                runid, run_modified_time = runid_pair
                if 'doclist_modified_time' in query:
                    print "Run modified time: " + str(run_modified_time)
                    print "Doclist modified time: " + str(query['doclist_modified_time'])
                    # Definitive delete after reactivation period
                    if query['doclist_modified_time'] - run_modified_time >= reactivation_period:
                        # Assumption: The cronjob is performed regularly, otherwise the
                        # reactivation period is shortened
                        print "Run is now past reactivation period, document list obsolete. Delete."
                        run_user = get_user(userid)
                        run_email = run_user["email"]
                        run_teamname = run_user["teamname"]
                        send_email({'email': run_email, 'teamname': run_teamname},
                               "Your run " + runid + " is past the reactivation period (document list obsolete) and will be deleted.",
                               "Run deleted")
                    # First warning, start of reactivation period
                    elif run_modified_time < query['doclist_modified_time']:
                        print("Run older than latest doclist, send email: ", runid, run_modified_time)
                        run_user = get_user(userid)
                        run_email = run_user["email"]
                        run_teamname = run_user["teamname"]
                        send_email({'email': run_email, 'teamname': run_teamname},
                                   "Your run " + runid + " is older than the corresponding document list, it will be deactivated in " + str(config["REACTIVATION_PERIOD_DAYS"]) + " days. If this run is valuable, you can reactivate it via " +
                                   config[
                                       "URL_REACTIVATION"] + " inside the reactivation period. After " + str(config["REACTIVATION_PERIOD_DAYS"]) + " days, it is not possible to reactivate anymore.",
                                   "Outdated run")

                        continue
                # Definitive delete after reactivation period
                if age_threshold - run_modified_time >= reactivation_period:
                    print "Run is now past reactivation period. Delete."
                    run_user = get_user(userid)
                    run_email = run_user["email"]
                    run_teamname = run_user["teamname"]
                    send_email({'email': run_email, 'teamname': run_teamname},
                               "Your outdated run " + runid + " is past the reactivation period and will be deleted.",
                               "Run deleted")
                    continue
                # First warning, start of reactivation period
                elif run_modified_time < age_threshold:
                    print("Run older than threshold, send e-mail: ", runid, run_modified_time)
                    run_user = get_user(userid)
                    run_email = run_user["email"]
                    run_teamname = run_user["teamname"]
                    send_email({'email': run_email, 'teamname': run_teamname},
                               "Your run " + runid + " is older than the set age threshold of " + str(config["RUN_AGE_THRESHOLD_DAYS"]) + " days. The run will be deleted in " + str(config["REACTIVATION_PERIOD_DAYS"]) + " days. If this run is valuable, you can reactivate it via " +
                               str(config[
                                   "URL_REACTIVATION"]) + " inside the reactivation period. After " + str(config["REACTIVATION_PERIOD_DAYS"]) + " days, it is not possible to reactivate anymore.",
                               "Outdated run")
                    continue
            else:
                print("Run not paired with timestamp, not able to clean up")
                continue

def db_cleanup():
    print "Database cleanup task started"
    age_threshold = datetime.datetime.now() - datetime.timedelta(days=config["RUN_AGE_THRESHOLD_DAYS"])
    reactivation_period = datetime.timedelta(days=config["REACTIVATION_PERIOD_DAYS"])

    # First delete runs, then notify outdated. Because there is overlap:
    # deletable runs is a subset of outdated runs
    deletable_runs_age, deletable_runs_doclist = core.run.get_deletable_runs()

    for run in deletable_runs_age:
        print "Run is now past reactivation period. Delete."
        db.user
        run_user = get_user(run["userid"])
        run_email = run_user["email"]
        run_teamname = run_user["teamname"]
        send_email({'email': run_email, 'teamname': run_teamname},
                   "Your outdated run " + run["runid"] + " is past the reactivation period and will be deleted.",
                   "Run deleted")

    for run in deletable_runs_doclist:
        print "Run is now past reactivation period, document list obsolete. Delete."
        run_user = get_user(run["userid"])
        run_email = run_user["email"]
        run_teamname = run_user["teamname"]
        send_email({'email': run_email, 'teamname': run_teamname},
               "Your run " + run["runid"] + " is past the reactivation period (document list obsolete) and will be deleted.",
               "Run deleted")

    outdated_runs_age, outdated_runs_doclist = core.run.get_outdated_runs()

    for run in outdated_runs_age:
        print("Run older than threshold, send e-mail: ", run["runid"], run["creation_time"])
        run_user = get_user(run["userid"])
        run_email = run_user["email"]
        run_teamname = run_user["teamname"]
        send_email({'email': run_email, 'teamname': run_teamname},
                   "Your run " + run["runid"] + " is older than the set age threshold of " + str(config["RUN_AGE_THRESHOLD_DAYS"]) + " days. The run will be deleted in " + str(config["REACTIVATION_PERIOD_DAYS"]) + " days. If this run is valuable, you can reactivate it via " +
                   str(config[
                       "URL_REACTIVATION"]) + " inside the reactivation period. After " + str(config["REACTIVATION_PERIOD_DAYS"]) + " days, it is not possible to reactivate anymore.",
                   "Outdated run")

    for run in outdated_runs_doclist:
        print("Run older than latest doclist, send email: ", run["runid"], run["creation_time"])
        run_user = get_user(run["userid"])
        run_email = run_user["email"]
        run_teamname = run_user["teamname"]
        send_email({'email': run_email, 'teamname': run_teamname},
                   "Your run " + run["runid"] + " is older than the corresponding document list, it will be deactivated in " + str(config["REACTIVATION_PERIOD_DAYS"]) + " days. If this run is valuable, you can reactivate it via " +
                   config[
                       "URL_REACTIVATION"] + " inside the reactivation period. After " + str(config["REACTIVATION_PERIOD_DAYS"]) + " days, it is not possible to reactivate anymore.",
                   "Outdated run")


def calculate_statistics():
    print "Calculate statistics"

    # Calculate site statistics
    sites = core.site.get_sites()
    for site in sites:
        site_id = site["_id"]
        feedbacks = core.db.db.feedback.find({"site_id": site_id})
        clicks = 0

        stats = {
                 "query": core.db.db.query.find({"site_id": site_id}).count(),
                 "doc": core.db.db.doc.find({"site_id": site_id}).count(),
                 "impression": feedbacks.count(),
                 "click": clicks,
        }
        stats_file = "stats_site_" + site_id + ".p"
        pickle.dump(stats,open(stats_file,"wb"))


app = Flask(__name__)
api = Api(app, catch_all_404s=True)

cron = BackgroundScheduler()
cron.add_job(db_cleanup, 'interval', id='cleanjob', hours=config["CLEANUP_INTERVAL_HOURS"])
cron.add_job(calculate_statistics, 'interval', id='statjob', hours=config["CALC_STATS_INTERVAL_HOURS"])


@app.before_first_request
def limit_request():
    if app.debug:
        return
    Limiter(app, global_limits=["300/minute", "10/second"],
            headers_enabled=True)

@app.before_first_request
def init_rollbar():
    """init rollbar module"""
    if app.debug:
        return
    rollbar.init(
        # access token for the demo app: https://rollbar.com/demo
        core.config.config["ROLLBAR_API_KEY"],
        # environment name
        core.config.config["ROLLBAR_ENV"],
        # server root directory, makes tracebacks prettier
        root=os.path.dirname(os.path.realpath(__file__)),
        # flask already sets up logging
        allow_logging_basic_config=False)

    # send exceptions from `app` to rollbar, using flask's signal system.
    got_request_exception.connect(rollbar.contrib.flask.report_exception, app)


@app.before_request
def before_request():
    g.start = time.time()


@app.after_request
def after_request(response):
    try:
        diff = int((time.time() - g.start) * 1000)
        response.headers.add('X-Execution-Time', str(diff))
    except:
        pass
    return response

@app.route("/")
def hello():
    return redirect(core.config.config["URL_DOC"])