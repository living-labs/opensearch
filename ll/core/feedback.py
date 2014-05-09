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

from db import db
import doc


def add_feedback(site_id, sid, feedback):
    existing_feedback = db.feedback.find_one({"site_id": site_id, "sid": sid})
    if existing_feedback == None:
        raise Exception("Session not found: sid = '%s'." % sid)
    for doc in feedback["doclist"]:
        doc_found = doc.get_doc(site_id=site_id, site_docid=doc["site_docid"])
        if not doc_found:
            raise Exception("Document not found: site_docid = '%s'. Please"
                            "only provide feedback for documents that are"
                            "allowed for a query." % doc["site_docid"])
        doc["docid"] = doc_found["_id"]
    for k in feedback:
        existing_feedback[k] = feedback[k]
    db.feedback.save(existing_feedback)
    return feedback


def get_feedback(participant_id=None, site_id=None, sid=None):
    q = {}
    if participant_id:
        q["participant_id"] = site_id
    if site_id:
        q["site_id"] = site_id
    if sid:
        q["sid"] = qid
    feedback = db.feedback.find_one(q)
    if not feedback:
        raise Exception("Feedback not found:  sid = '%s'" % site_qid)
    return feedback
