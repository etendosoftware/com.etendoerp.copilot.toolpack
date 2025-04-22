package com.etendoerp.copilot.toolpack.webhook;

import static org.junit.Assert.assertTrue;

import java.util.HashMap;
import java.util.Map;

import org.apache.commons.lang3.StringUtils;
import org.codehaus.jettison.json.JSONObject;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.mockito.MockitoAnnotations;
import org.openbravo.base.secureApp.VariablesSecureApp;
import org.openbravo.base.session.OBPropertiesProvider;
import org.openbravo.base.weld.test.WeldBaseTest;
import org.openbravo.client.kernel.RequestContext;
import org.openbravo.dal.core.OBContext;
import org.openbravo.dal.service.OBDal;
import org.openbravo.test.base.TestConstants;

import com.etendoerp.copilot.toolpack.webhooks.ExecSQL;
import com.etendoerp.copilot.toolpack.webhooks.SimSearch;

/**
 * Unit tests for the Webhooks in the Copilot Toolpack.
 *
 */

public class WebhooksTests extends WeldBaseTest {
  public static final String DATA = "data";
  public static final String ID = "id";
  private AutoCloseable mocks;

  /**
   * Sets up the test environment before each test.
   *
   * @throws Exception
   *     if an error occurs during setup
   */
  @Before
  public void setUp() throws Exception {
    mocks = MockitoAnnotations.openMocks(this);
    super.setUp();

    OBContext.setOBContext(TestConstants.Users.ADMIN, TestConstants.Roles.SYS_ADMIN, TestConstants.Clients.SYSTEM,
        TestConstants.Orgs.MAIN);
    VariablesSecureApp vars = new VariablesSecureApp(OBContext.getOBContext().getUser().getId(),
        OBContext.getOBContext().getCurrentClient().getId(), OBContext.getOBContext().getCurrentOrganization().getId());
    RequestContext.get().setVariableSecureApp(vars);

    OBDal.getInstance().flush();

    vars.setSessionValue("#User_Client", OBContext.getOBContext().getCurrentClient().getId());
    RequestContext.get().setVariableSecureApp(vars);
    OBPropertiesProvider.setInstance(new OBPropertiesProvider());
  }

  /**
   * Tests the execSQLWebhook method.
   * <p>
   * This test method verifies the functionality of the execSQLWebhook method in the ExecSQL class.
   * It tests different modes of SQL execution and checks the responses.
   * </p>
   *
   * @throws Exception
   *     if an error occurs during the test
   */
  @Test
  public void execSQLWebhook() {
    ExecSQL ex = new ExecSQL();
    Map<String, String> parameter = new HashMap<>();
    Map<String, String> respVars;

    // Test SHOW_TABLES mode
    parameter.put("Mode", "SHOW_TABLES");
    respVars = new HashMap<>();
    ex.get(parameter, respVars);
    assertTrue(!respVars.keySet().isEmpty());

    // Test SHOW_COLUMNS mode
    parameter.put("Mode", "SHOW_COLUMNS");
    parameter.put("Table", "C_BPartner");
    respVars = new HashMap<>();
    ex.get(parameter, respVars);
    assertTrue(!respVars.keySet().isEmpty());

    // Test EXEC mode with a query that should fail
    try {
      parameter.put("Mode", "EXEC");
      parameter.put("Query", "SELECT * FROM ad_field");
      respVars = new HashMap<>();
      ex.get(parameter, respVars);
    } catch (Exception e) {
      // The message must be "The table ad_field must have an alias."
      assertTrue(StringUtils.containsIgnoreCase(e.getMessage(), "The table ad_field must have an alias."));
    }

    // Test EXEC mode with a valid query
    parameter.put("Mode", "EXEC");
    parameter.put("Query", "SELECT * FROM ad_field af");
    respVars = new HashMap<>();
    ex.get(parameter, respVars);
    assertTrue(!respVars.keySet().isEmpty());
    assertTrue(StringUtils.isNotEmpty(respVars.get("data")));
  }

  /**
   * Tests the simSearch method.
   * <p>
   * This test method verifies the functionality of the simSearch method in the SimSearch class.
   * It tests the search functionality and checks the responses.
   * </p>
   *
   * @throws Exception
   *     if an error occurs during the test
   */
  @Test
  public void simSearch() throws Exception {
    SimSearch ss = new SimSearch();
    Map<String, String> parameter = new HashMap<>();
    Map<String, String> respVars;

    // Test search with a search term and entity name
    parameter.put("searchTerm", "c_order");
    parameter.put("entityName", "ADTable");
    respVars = new HashMap<>();
    ss.get(parameter, respVars);
    assertTrue(!respVars.keySet().isEmpty());
    assertTrue(StringUtils.isNotEmpty(respVars.get("message")));
    JSONObject json = new JSONObject(respVars.get("message"));
    assertTrue(json.has("data"));
    assertTrue(json.getJSONArray("data").length() > 0);
  }

  /**
   * Cleans up the test environment after each test.
   */
  @After
  public void tearDown() {
    OBContext.setOBContext(TestConstants.Users.ADMIN, TestConstants.Roles.SYS_ADMIN, TestConstants.Clients.SYSTEM,
        TestConstants.Orgs.MAIN);
    VariablesSecureApp vars = new VariablesSecureApp(OBContext.getOBContext().getUser().getId(),
        OBContext.getOBContext().getCurrentClient().getId(), OBContext.getOBContext().getCurrentOrganization().getId());
    RequestContext.get().setVariableSecureApp(vars);
    OBDal.getInstance().flush();
    OBDal.getInstance().commitAndClose();
  }
}
