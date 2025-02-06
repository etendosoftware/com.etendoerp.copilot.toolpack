package com.etendoerp.copilot.toolpack;
import java.util.HashMap;
import java.util.Map;

import org.hibernate.dialect.function.SQLFunction;
import org.hibernate.dialect.function.StandardSQLFunction;
import org.hibernate.type.StandardBasicTypes;
import org.openbravo.dal.core.SQLFunctionRegister;

public class SqlToHqlInitializer implements SQLFunctionRegister {

  @Override
  public Map<String, SQLFunction> getSQLFunctions() {
    Map<String, SQLFunction> sqlFunctions = new HashMap<>();

    sqlFunctions.put("etcotp_sim_search",
        new StandardSQLFunction("etcotp_sim_search", StandardBasicTypes.BIG_DECIMAL));
    return sqlFunctions;
  }
}
