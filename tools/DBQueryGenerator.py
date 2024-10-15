from typing import Type, Dict, Optional

from langsmith import traceable

from copilot.core import utils
from copilot.core.threadcontext import ThreadContext
from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolWrapper
from copilot.core.utils import copilot_debug


class DBEtendoToolInput(ToolInput):
    p_mode: str = ToolField(
        title="Mode",
        description='This parameter indicates the mode of the tool. '
                    'The mode can be SHOW_TABLES, SHOW_COLUMNS, EXECUTE_QUERY.'
                    ' SHOW_TABLES will return the tables of the database, with the table name, name and description.'
                    ' SHOW_COLUMNS will return the columns of a table, with the column name, name and description.'
                    ' EXECUTE_QUERY will execute the query that the user wants.',
        enum=['SHOW_TABLES', 'SHOW_COLUMNS', 'EXECUTE_QUERY']
    )
    p_data: Optional[str] = ToolField(
        title="Data",
        description="The data that the user wants to get from the database. The data is used in the mode SHOW_COLUMNS "
                    "and EXECUTE_QUERY."
                    " In the mode SHOW_COLUMNS, the data is the table name."
                    " In the mode EXECUTE_QUERY, the data is the query that the user wants to execute."
                    "In other modes, this parameter is not used."
    )


def _get_headers(access_token: Optional[str]) -> Dict:
    """
    This method generates headers for an HTTP request.

    Parameters:
    access_token (str, optional): The access token to be included in the headers. If provided, an 'Authorization' field
     is added to the headers with the value 'Bearer {access_token}'.

    Returns:
    dict: A dictionary representing the headers. If an access token is provided, the dictionary includes an
     'Authorization' field.
    """
    headers = {}

    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


@traceable
def exec_sql(query: str, security_check: bool = True):
    import requests
    import json

    extra_info = ThreadContext.get_data('extra_info')
    if extra_info is None or extra_info.get('auth') is None or extra_info.get('auth').get('ETENDO_TOKEN') is None:
        return {"error": "No access token provided, to work with Etendo, an access token is required."
                         "Make sure that the Webservices are enabled to the user role and the WS are configured for"
                         " the Entity."
                }
    access_token = extra_info.get('auth').get('ETENDO_TOKEN')
    url = utils.read_optional_env_var("ETENDO_HOST", "http://host.docker.internal:8080/etendo")
    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    endpoint = "/webhooks/?name=DBQueryExec"
    body_params = {
        "Query": query,
        "SecurityCheck": security_check
    }

    json_data = json.dumps(body_params)
    post_result = requests.post(url=(url + endpoint), data=json_data, headers=headers)
    if post_result.ok:
        return json.loads(post_result.text)
    else:
        copilot_debug(post_result.text)
        return {"error": post_result.text}


@traceable
def show_tables():
    return exec_sql("SELECT t.TABLENAME,"
                    "t.NAME,"
                    " t.DESCRIPTION"
                    " FROM AD_TABLE t "
                    "where checkReadableEntities(t) ", True)


@traceable
def show_columns(table_name):
    sql = f"""
    SELECT
        col.columnname,
        col.name,
        col.description
    FROM
        AD_COLUMN col
        INNER JOIN AD_TABLE tabl on tabl.ad_table_id = col.ad_table_id
    WHERE
        tabl.tablename ILIKE '{table_name}'; """

    columns = exec_sql(sql, False)

    return columns


class DBQueryGenerator(ToolWrapper):
    name = 'DBQueryGenerator'
    description = (
        ''' 
        This tool can connect to a database and read data from it.
        This tool has three modes: SHOW_TABLES, SHOW_COLUMNS, EXECUTE_QUERY.
        The mode SHOW_TABLES will return the tables of the database, with the table name, name and description.
        The mode SHOW_COLUMNS will return the columns of a table, with the column name, name and description. This mode 
        needs the parameter p_data with the table name.
        The mode EXECUTE_QUERY will execute the query that the user wants. This mode needs the parameter p_data with 
        the query.
        ''')

    args_schema: Type[ToolInput] = DBEtendoToolInput

    @traceable
    def run(self, input_params: Dict, *args, **kwargs):

        # Get the input parameters, if the parameter is not defined, the default value is used.
        p_mode = input_params.get('p_mode')
        p_data = input_params.get('p_data')

        error_wrong_mode = {
            "error": "The mode parameter is mandatory and must be one of the following values: SHOW_TABLES, "
                     "SHOW_COLUMNS, EXECUTE_QUERY"
        }
        if p_mode is None or p_mode not in ['SHOW_TABLES', 'SHOW_COLUMNS', 'EXECUTE_QUERY']:
            return error_wrong_mode
        if p_mode == 'SHOW_TABLES':
            return show_tables()
        elif p_mode == 'SHOW_COLUMNS':
            if p_data is None:
                return {"error": "The data parameter is mandatory in the mode SHOW_COLUMNS."}
            return show_columns(table_name=p_data)
        elif p_mode == 'EXECUTE_QUERY':
            if p_data is None:
                return {"error": "The data parameter is mandatory in the mode EXECUTE_QUERY."}
            return exec_sql(p_data)
        else:
            return error_wrong_mode
