package com.etendoerp.copilot.toolpack.webhooks;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import org.apache.commons.lang.StringUtils;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.codehaus.jettison.json.JSONArray;
import org.hibernate.criterion.Restrictions;
import org.openbravo.base.exception.OBException;
import org.openbravo.base.model.Entity;
import org.openbravo.dal.core.OBContext;
import org.openbravo.dal.service.OBCriteria;
import org.openbravo.dal.service.OBDal;
import org.openbravo.erpCommon.utility.OBMessageUtils;
import org.openbravo.model.ad.datamodel.Column;
import org.openbravo.model.ad.datamodel.Table;

import com.etendoerp.webhookevents.services.BaseWebhookService;

import net.sf.jsqlparser.JSQLParserException;
import net.sf.jsqlparser.expression.StringValue;
import net.sf.jsqlparser.expression.operators.conditional.AndExpression;
import net.sf.jsqlparser.expression.operators.relational.ExpressionList;
import net.sf.jsqlparser.expression.operators.relational.InExpression;
import net.sf.jsqlparser.expression.operators.relational.ParenthesedExpressionList;
import net.sf.jsqlparser.parser.CCJSqlParserUtil;
import net.sf.jsqlparser.statement.Statement;
import net.sf.jsqlparser.statement.StatementVisitorAdapter;
import net.sf.jsqlparser.statement.select.FromItemVisitorAdapter;
import net.sf.jsqlparser.statement.select.PlainSelect;
import net.sf.jsqlparser.statement.select.Select;
import net.sf.jsqlparser.statement.select.SelectVisitorAdapter;

/**
 * The ExecSQL class handles the execution of SQL queries received through a webhook and returns the result in JSON format.
 * It also provides optional security checks on the query before execution.
 */
public class ExecSQL extends BaseWebhookService {

  private static final Logger log = LogManager.getLogger();
  public static final String DO_SECURITY_CHECK = "doSecurityCheck";

  /**
   * Executes an SQL query received in the parameter map and stores the result in the response map.
   * The result is returned in JSON format, including the executed query, columns, and data.
   * If a security check is requested, it modifies the query to include security constraints.
   *
   * @param parameter
   *     a map of parameters, including the SQL query and security flag
   * @param responseVars
   *     a map to store the response, including query result and potential errors
   */
  @Override
  public void get(Map<String, String> parameter, Map<String, String> responseVars) {
    logIfDebug("Executing process");
    for (Map.Entry<String, String> entry : parameter.entrySet()) {
      logIfDebug(String.format("Parameter: %s = %s", entry.getKey(), entry.getValue()));
    }
    String query = null;
    Connection conn = null;
    try {
      String mode = parameter.get("Mode");
      query = parameter.get("Query");
      String table = parameter.get("Table");

      conn = OBDal.getInstance().getConnection();

      if (StringUtils.equalsIgnoreCase(mode, "SHOW_TABLES")) {
        handleShowTable(responseVars);
      } else if (StringUtils.equalsIgnoreCase(mode, "SHOW_COLUMNS")) {
        if (StringUtils.isEmpty(table)) {
          responseVars.put("error", OBMessageUtils.messageBD("ETCOPTP_NoTable")); //Ver message
          return;
        }
        handleShowColumns(responseVars, table, conn);
      } else {
        if (StringUtils.isEmpty(query)) {
          responseVars.put("error", OBMessageUtils.messageBD("ETCOPTP_NoQuery"));
          return;
        }
        handleExecuteQuery(responseVars, query, conn);
      }


    } catch (JSQLParserException e) {
      responseVars.put("error", e.getMessage());
      return;
    }
  }

  /**
   * Executes an SQL query received in the parameter map and stores the result in the response map.
   * The result is returned in JSON format, including the executed query, columns, and data.
   * If a security check is requested, it modifies the query to include security constraints.
   *
   * @param responseVars
   *     a map to store the response, including query result and potential errors
   * @param query
   *     the SQL query to be executed
   * @param conn
   *     the database connection to use for executing the query
   * @throws JSQLParserException
   *     if there is an error parsing the SQL statement
   */
  private void handleExecuteQuery(Map<String, String> responseVars, String query,
      Connection conn) throws JSQLParserException {

    // Parse the query
    Statement statement = CCJSqlParserUtil.parse(query);

    // Validations
    validateIsSelect(statement);
    validateAllTablesHaveAliases(statement);
    validateAccessibleTables(statement);

    // Modify WHERE clause
    addSecurityFilters(statement);
    query = statement.toString();
    try (PreparedStatement stat = conn.prepareStatement(query)) {
      ResultSet result = stat.executeQuery();

      // Prepare the response as a JSON object
      int columnCount = result.getMetaData().getColumnCount();
      JSONArray columns = new JSONArray();
      for (int i = 1; i <= columnCount; i++) {
        columns.put(result.getMetaData().getColumnName(i));
      }
      JSONArray data = new JSONArray();
      while (result.next()) {
        JSONArray row = new JSONArray();
        for (int i = 1; i <= columnCount; i++) {
          row.put(result.getString(i));
        }
        data.put(row);
      }
      responseVars.put("queryExecuted", query);
      responseVars.put("columns", columns.toString());
      responseVars.put("data", data.toString());
    } catch (SQLException e) {
      throw new OBException(" ERROR"); //TODO
    }

  }

  /**
   * Adds security filters to the given SQL statement.
   * <p>
   * This method modifies the WHERE clause of the provided SQL statement to include security constraints
   * based on the readable client and organization IDs.
   *
   * @param statement
   *     the SQL statement to modify
   */
  private void addSecurityFilters(Statement statement) {
    SelectVisitorAdapter<Void> selectVisitorAdapter = new SelectVisitorAdapter<>() {
      @Override
      public <S> Void visit(PlainSelect plainSelect, S context) {
        InExpression clientValidation = new InExpression();
        String alias = plainSelect.getFromItem().getAlias().getName();
        clientValidation.setLeftExpression(new net.sf.jsqlparser.schema.Column(alias + ".ad_client_id"));
        clientValidation.setRightExpression(convertToArrayExpression(getClientreadableSet()));

        InExpression orgValidation = new InExpression();
        orgValidation.setLeftExpression(new net.sf.jsqlparser.schema.Column(alias + ".ad_org_id"));
        orgValidation.setRightExpression(convertToArrayExpression(getOrganizationReadableSet()));

        AndExpression cliAndOrgValidations = new AndExpression(clientValidation, orgValidation);

        if (plainSelect.getWhere() == null) {
          plainSelect.setWhere(cliAndOrgValidations);
        } else {
          plainSelect.setWhere(
              new AndExpression(plainSelect.getWhere(),
                  cliAndOrgValidations));
        }
        return null;
      }
    };

    StatementVisitorAdapter<Void> statementVisitor = new StatementVisitorAdapter<>() {
      public <S> Void visit(Select select, S context) {
        return select.getPlainSelect().accept(selectVisitorAdapter, context);
      }
    };
    statement.accept(statementVisitor, null);
  }

  /**
   * Converts an array of readable client or organization IDs to an ExpressionList of StringValue.
   * <p>
   * This method takes an array of readable client or organization IDs and converts each ID into a StringValue.
   * The resulting StringValues are then added to an ExpressionList.
   *
   * @param clientreadableSet
   *     An array of readable client or organization IDs.
   * @return An ExpressionList containing the StringValues of the provided IDs.
   */
  private ExpressionList<StringValue> convertToArrayExpression(String[] clientreadableSet) {
    ArrayList<StringValue> values = new ArrayList<>();
    for (String s : clientreadableSet) {
      values.add(new StringValue(s));
    }
    return new ParenthesedExpressionList<StringValue>(values);
  }

  /**
   * Validates that the given SQL statement is a SELECT statement.
   * <p>
   * This method checks if the provided SQL statement is an instance of the Select class.
   * If it is not, it throws an OBException.
   *
   * @param statement
   *     The SQL statement to validate.
   * @throws OBException
   *     If the statement is not a SELECT statement.
   */
  public void validateIsSelect(Statement statement) {
    if (!(statement instanceof Select)) {
      throw new OBException(OBMessageUtils.messageBD("ETCOPTP_OnlySelect")); //TODO: Ver mensaje
    }
  }

  /**
   * Validates that all tables in the given SQL statement are accessible.
   * <p>
   * This method extracts all tables from the provided SQL statement and checks if each table is accessible
   * based on the current context. If any table is not accessible, it throws an OBException.
   *
   * @param statement
   *     The SQL statement to validate.
   * @throws JSQLParserException
   *     If there is an error parsing the SQL statement.
   * @throws OBException
   *     If any table is not accessible.
   */
  public void validateAccessibleTables(Statement statement) throws JSQLParserException {
    List<net.sf.jsqlparser.schema.Table> tables = extractAllTables(statement);
    List<String> tablesAccesable = getTablesOfAD().stream()
        .map(Table::getDBTableName)
        .collect(Collectors.toList());
    for (net.sf.jsqlparser.schema.Table table : tables) {
      String tableName = table.getName();
      if (tablesAccesable.stream().noneMatch(t -> StringUtils.equalsIgnoreCase(t, tableName))) {
        throw new OBException(
            String.format(OBMessageUtils.messageBD("ETCOPTP_TableNotAccessible"), tableName)); //TODO: Ver mensaje
      }
    }
  }

  /**
   * Extracts all tables from the given SQL statement.
   * <p>
   * This method defines visitors to traverse the SQL statement and collect all tables into a list.
   *
   * @param statement
   *     The SQL statement to extract tables from.
   * @return A list of tables extracted from the SQL statement.
   */
  private List<net.sf.jsqlparser.schema.Table> extractAllTables(Statement statement) {
    List<net.sf.jsqlparser.schema.Table> tables = new ArrayList<>();

    // Define an Expression Visitor reacting on any Expression
    FromItemVisitorAdapter<Void> fromItemVisitorAdapter = new FromItemVisitorAdapter<>() {
      public <S> Void visit(net.sf.jsqlparser.schema.Table table, S context) {
        tables.add(table);
        return null;
      }
    };

    // Define a Select Visitor reacting on a Plain Select invoking the Expression Visitor on the Where Clause
    SelectVisitorAdapter<Void> selectVisitorAdapter = new SelectVisitorAdapter<>() {
      @Override
      public <S> Void visit(PlainSelect plainSelect, S context) {
        return plainSelect.getFromItem().accept(fromItemVisitorAdapter, context);
      }
    };

    StatementVisitorAdapter<Void> statementVisitor = new StatementVisitorAdapter<>() {
      public <S> Void visit(Select select, S context) {
        return select.getPlainSelect().accept(selectVisitorAdapter, context);
      }
    };

    statement.accept(statementVisitor, null);
    return tables;
  }

  /**
   * Validates that all tables in the given SQL statement have aliases.
   * <p>
   * This method extracts all tables from the provided SQL statement and checks if each table has an alias.
   * If any table does not have an alias, it throws an OBException.
   *
   * @param statement
   *     The SQL statement to validate.
   * @throws JSQLParserException
   *     If there is an error parsing the SQL statement.
   * @throws OBException
   *     If any table does not have an alias.
   */
  public void validateAllTablesHaveAliases(Statement statement) throws JSQLParserException {
    List<net.sf.jsqlparser.schema.Table> tables = extractAllTables(statement);
    for (net.sf.jsqlparser.schema.Table table : tables) {
      if (table.getAlias() == null || StringUtils.isEmpty(table.getAlias().getName())) {
        throw new OBException(
            String.format(OBMessageUtils.messageBD("ETCOPTP_TableWithoutAlias"), table.getName())); //TODO: Ver mensaje
      }
    }
  }

  /**
   * Handles the retrieval of column information for a specific table and stores it in the response map.
   * <p>
   * This method retrieves column information from the application dictionary and the database schema,
   * formats the information into a JSON array, and stores it in the response map.
   *
   * @param responseVars
   *     A map to store the response, including column information.
   * @param table
   *     The name of the table to retrieve column information for.
   * @param conn
   *     The database connection to use for retrieving column information.
   */
  private void handleShowColumns(Map<String, String> responseVars, String table, Connection conn) {
    OBCriteria<Table> criteria = OBDal.getInstance().createCriteria(Table.class);
    criteria.add(Restrictions.or(Restrictions.ilike(Table.PROPERTY_DBTABLENAME, table),
        Restrictions.ilike(Table.PROPERTY_NAME, table)));
    criteria.setMaxResults(1);
    Table tableObj = (Table) criteria.uniqueResult();
    if (tableObj == null) {
      responseVars.put("error", OBMessageUtils.messageBD("ETCOPTP_NoTable"));
      return;
    }
    List<Column> colADColumn = tableObj.getADColumnList();
    String sql = "SELECT column_name, " +
        "data_type " +
        "FROM information_schema.columns " +
        "WHERE UPPER(table_name) = UPPER(?)";
    try (PreparedStatement statement = conn.prepareStatement(sql)) {
      statement.setString(1, tableObj.getDBTableName());
      ResultSet result = statement.executeQuery();
      JSONArray data = new JSONArray();
      data.put(new JSONArray(Arrays.asList("COLUMNNAME", "NAME", "DBTYPE", "DESCRIPTION")));
      while (result.next()) {
        JSONArray row = new JSONArray();
        String columnName = result.getString(1);
        row.put(columnName);
        colADColumn.stream().filter(c -> StringUtils.equalsIgnoreCase(c.getDBColumnName(), columnName)).findFirst()
            .ifPresent(c -> {
              row.put(c.getName());
              try {
                row.put(result.getString(2));
              } catch (SQLException e) {
                row.put("?");
              }
              row.put(c.getDescription());
            });
        data.put(row);
      }
      responseVars.put("data", data.toString());
    } catch (Exception e) {
      responseVars.put("error", e.getMessage());
    }
  }

  /**
   * Handles the retrieval of table information and stores it in the response map.
   * <p>
   * This method retrieves a list of tables from the application dictionary and formats the information
   * into a JSON array, which is then stored in the response map.
   *
   * @param responseVars
   *     a map to store the response, including table information
   */
  private static void handleShowTable(Map<String, String> responseVars) {
    List<Table> tableList = getTablesOfAD();

    JSONArray data = new JSONArray();
    data.put(new JSONArray(Arrays.asList("TABLENAME", "NAME", "DESCRIPTION")));
    for (Table table : tableList) {
      JSONArray row = new JSONArray();
      row.put(table.getDBTableName());
      row.put(table.getName());
      row.put(table.getDescription());
      data.put(row);
    }
    responseVars.put("data", data.toString());
  }

  /**
   * Retrieves a list of tables from the application dictionary.
   * <p>
   * This method creates a criteria query to find all tables that are accessible based on the current context.
   *
   * @return a list of accessible tables
   */
  private static List<Table> getTablesOfAD() {
    OBCriteria<Table> criteria = OBDal.getInstance().createCriteria(Table.class);
    List<String> accesableTablesID = getAccesableTablesID();
    criteria.add(Restrictions.in(Table.PROPERTY_ID, accesableTablesID));
    List<Table> tableList = criteria.list();
    return tableList;
  }

  /**
   * Retrieves a list of accessible table IDs based on the current context.
   * <p>
   * This method retrieves the IDs of all tables that are writable based on the current user's context.
   *
   * @return a list of accessible table IDs
   */
  private static List<String> getAccesableTablesID() {
    return OBContext.getOBContext().getEntityAccessChecker().getWritableEntities().stream()
        .map(Entity::getTableId).collect(Collectors.toList());
  }

  /**
   * Logs a message in debug mode if debug logging is enabled.
   *
   * @param s
   *     the message to be logged
   */
  private void logIfDebug(String s) {
    if (log.isDebugEnabled()) {
      log.debug(s);
    }
  }

  /**
   * Retrieves the set of readable client IDs based on the current context.
   * <p>
   * This method retrieves the IDs of all clients that are readable based on the current user's context.
   *
   * @return an array of readable client IDs
   */
  private String[] getClientreadableSet() {
    return OBContext.getOBContext().getReadableClients();
  }

  /**
   * Retrieves the set of readable organization IDs based on the current context.
   * <p>
   * This method retrieves the IDs of all organizations that are readable based on the current user's context.
   *
   * @return an array of readable organization IDs
   */
  private String[] getOrganizationReadableSet() {
    return OBContext.getOBContext().getReadableOrganizations();
  }

}
