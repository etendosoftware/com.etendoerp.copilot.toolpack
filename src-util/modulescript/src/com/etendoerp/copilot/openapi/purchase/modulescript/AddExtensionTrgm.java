
package com.etendoerp.copilot.openapi.purchase.modulescript;

import java.sql.PreparedStatement;

import org.openbravo.database.ConnectionProvider;
import org.openbravo.modulescript.ModuleScript;

public class AddExtensionTrgm extends ModuleScript {

  public void execute() {
    try {
      ConnectionProvider cp = getConnectionProvider();
      PreparedStatement ps = cp
          .getPreparedStatement("create extension if not exists pg_trgm;");
      ps.executeUpdate();
    } catch (Exception e) {
      handleError(e);
    }
  }
}
