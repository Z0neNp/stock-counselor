from common.loggable_api import Loggable
from datetime import datetime
from data_gathering_worker_service.backend_tasks_api import BackendTasks
from data_gathering_worker_service.entity_api import Entity
from data_gathering_worker_service.sec_communicator_api import SecCommunicator
from enum import Enum
from logging import getLogger, DEBUG, FileHandler, Formatter
from time import sleep

class GatheringProgress(Enum):
  QUERYING_FOR_10K_REPORT_CONTENTS = "Looking for the 10-K Report Contents at the SEC website"
  QUERYING_FOR_10K_IDS = "Looking for Company 10-K Report Ids at the SEC website"
  QUERYING_FOR_AVAILABLE_10K_REPORTS = "Looking for the Available Company 10-K Reports at the SEC website"
  QUERYING_FOR_10K_REPORT = "Looking for the Company 10-K Report at the SEC website"
  QUERYING_FOR_COMPANY_ID = "Looking for the Company Id at the SEC website"
  QUERYING_FOR_FINANCIAL_STMNT_CONTENTS = "Looking for the Financial Statement Contents at the SEC website"
  QUERYING_FOR_FINANCIAL_STMNT_TYPES = "Looking for Company 10-K Financial Statements Types at the SEC website"

class Worker(Loggable):
  """
  Reveals an external API for executing the backend tasks related to the financial data gathering.
  """

  def __init__(self):
    super().__init__("data_gathering_worker_service", "Worker")
    self._log_id = "data_gathering_worker_service"
    self._backend_tasks = BackendTasks(self._log_id)
    self._entity = Entity(self._log_id)
    self._sec_communicator = SecCommunicator(self._log_id)

  def startDataGatheringWorkerService(self):
    self._setupLogger()
    while True:
      acronym = self._getCompanyAcronymForGathering()

      if acronym is None:
        sleep(5)
        continue

      company_financial_data = self._getFinancialData(acronym)
      if company_financial_data:
        self._persistFinancialData(company_financial_data)

  def _getCompanyAcronymForGathering(self):
    """
    Returns a str or None.
    """
    self._debug("_getCompanyAcronymForGathering", "Start")
    result = self._backend_tasks.getCompanyAcronymFromNewTask()
    self._debug("_getCompanyAcronymForGathering", "Finish - result: %s\n" % result)
    return result

  def _getFinancialData(self, acronym):
    """
    Returns a dict. It contains:
     - acronym -- str
     - currency_units -- str
     - data_from_source -- dict
    Keyword arguments:
      acronym -- str -- an unique identifier of a company at a stock exchange (i.e. NASDAQ).
    """
    self._debug("_getFinancialData", "Start - acronym: %s" % acronym)
    result = {
      "acronym": acronym,
      "currency_units": None,
      "data_from_source": dict()
    }
    self._backend_tasks.updateTaskByCompanyAcronym(acronym, GatheringProgress.QUERYING_FOR_COMPANY_ID.value)
    company_id = self._sec_communicator.getCompanyId(acronym)

    if company_id:
      self._backend_tasks.updateTaskByCompanyAcronym(
        acronym, GatheringProgress.QUERYING_FOR_AVAILABLE_10K_REPORTS.value
      )
      html_with_10k_search_results = self._sec_communicator.get10kReportsSearchResults(company_id)

      if html_with_10k_search_results:
        self._backend_tasks.updateTaskByCompanyAcronym(acronym, GatheringProgress.QUERYING_FOR_10K_IDS.value)
        accession_numbers = self._sec_communicator.get10kAccessionNumbers(html_with_10k_search_results)

        if accession_numbers:
          pivot_date = datetime.strptime("2015-01-01", '%Y-%m-%d')
          for date_str, accession_number in accession_numbers.items():
            next_date = datetime.strptime(date_str, '%Y-%m-%d')
            if next_date < pivot_date:
              continue
            result["data"][date_str] = dict()
            self._backend_tasks.updateTaskByCompanyAcronym(
              acronym, GatheringProgress.QUERYING_FOR_10K_REPORT_CONTENTS.value
            )
            html_with_10k_report = self._sec_communicator.get10KReport(company_id, accession_number)

            if not html_with_10k_report:
              continue

            self._backend_tasks.updateTaskByCompanyAcronym(
              acronym, GatheringProgress.QUERYING_FOR_FINANCIAL_STMNT_TYPES.value
            )
            financial_statement_types = self._sec_communicator.getFinancialStatementsTypes(html_with_10k_report)

            for financial_statement_type in financial_statement_types:
              self._backend_tasks.updateTaskByCompanyAcronym(
                acronym, GatheringProgress.QUERYING_FOR_FINANCIAL_STMNT_CONTENTS.value
              )
              html_with_financial_statement = self._sec_communicator.getFinancialStatement(
                company_id,
                accession_number,
                financial_statement_type
              )

              if not html_with_financial_statement:
                continue

              financial_data = self._sec_communicator.getDataFromFinancialStatement(html_with_financial_statement)
              if not result["currency_units"] and financial_data[1]:
                result["currency_units"] = financial_data[1]
              result["data"][date_str] = result["data"][date_str] | financial_data[0]

    self._debug("_getFinancialData", "Finish - result: %s \n" % result)
    return result

  def _setupLogger(self):
    logger = getLogger(self._log_id)
    logger.setLevel(DEBUG)
    file_handler = FileHandler("%s.log" % self._log_id)
    file_handler.setLevel(DEBUG)
    file_handler.setFormatter(Formatter("%(msg)s"))
    logger.addHandler(file_handler)