"""
Reveals an internal API for retrieving data from U.S. Securities And Exchange Commission
"""

from json import dumps, load
from logging import getLogger
from os import listdir, path
from requests import post


class SecCommunicatorApi:

  """
  urls - JSON
  """
  def __init__(self):
    self._urls = self._loadUrls()

  def getCompanyIdWithAcronym(self, acronym):
    msg = '%s - %s() - Start - acronym: %s' % (
      "SecCommunicatorApi",
      "getCompanyIdWithAcronym",
      acronym
    )
    getLogger('data-gathering-worker-service').debug(msg)

    result = None
    config = self._urls["obtain_company_id"]
    dst_url = config["url"]
    req_headers = config["headers"]
    req_payload = config["payload"]
    req_payload["keysTyped"] = acronym

    try:
      res = post(dst_url, data=dumps(req_payload), headers=req_headers)

      if not res.status_code == 200:
        err_msg = "actual response status code VS expected: %d VS %d" % (res.status_code, 200)
        raise RuntimeError(err_msg)

      if not res.headers["Content-Type"] == req_headers["Accept"]:
        err_msg = "actual response content-type VS expected: %s VS %s" % (
          res.headers["Content-Type"],
          req_headers["Accept"]
        )
        raise RuntimeError(err_msg)

      res_payload = res.json()
      actual_acronym = res_payload["hits"]["hits"][0]["_source"]["tickers"].lower()

      if not actual_acronym == acronym:
        err_msg = "actual response acronym VS expected: %s VS %s" % (
          actual_acronym,
          acronym
        )
        raise RuntimeError(err_msg)
      result = res_payload["hits"]["hits"][0]["_id"]

    except (IndexError, RuntimeError) as err:
      msg = '%s - %s() - Error - %s' % (
        "SecCommunicatorApi",
        "getCompanyIdWithAcronym",
        err
      )
      getLogger('data-gathering-worker-service').error(msg)

    finally:
      msg = '%s - %s() - Finish - result: %s' % (
        "SecCommunicatorApi",
        "getCompanyIdWithAcronym",
        result
      )
      getLogger('data-gathering-worker-service').debug(msg)

      return result

  def _getRelativeLocationOfUrlsFile(self):
    return path.join(
      path.dirname( __file__ ),
      "sec_communicator",
      'urls.json'
    )

  def _loadUrls(self):
    result = None
    with open(self._getRelativeLocationOfUrlsFile(), "r") as read_file:
        result = load(read_file)

    return result


