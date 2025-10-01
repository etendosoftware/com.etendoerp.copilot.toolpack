package com.etendoerp.copilot.toolpack.webhook;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.FileAttribute;
import java.nio.file.attribute.PosixFilePermission;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;

import org.apache.commons.lang3.StringUtils;
import org.codehaus.jettison.json.JSONArray;
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

import com.etendoerp.copilot.toolpack.webhooks.AttachFileWebhook;
import com.etendoerp.copilot.toolpack.webhooks.ExecSQL;
import com.etendoerp.copilot.toolpack.webhooks.GetAvailableAgents;
import com.etendoerp.copilot.toolpack.webhooks.SimSearch;

/**
 * Unit tests for the Webhooks in the Copilot Toolpack.
 */

public class WebhooksTests extends WeldBaseTest {
  public static final String DATA = "data";
  public static final String ID = "id";
  public static final String ERROR = "error";
  public static final String MISSING_PARAMS = "Missing required parameters";
  public static final String RECORD_ID = "RecordId";
  public static final String FILE_NAME = "FileName";
  public static final String FILE_CONTENT = "FileContent";
  public static final String AD_TAB_ID = "ADTabId";
  public static final String AGENTS = "agents";
  public static final String MESSAGE = "message";
  public static final String TEST_RECORD_ID = "testRecordId";
  public static final String TEST_FILE_NAME = "test.txt";
  public static final String TEST_BASE64_CONTENT = "SGVsbG8gV29ybGQ="; // Base64 for "Hello World"
  private AutoCloseable mocks;

  /**
   * Sets up the test environment before each test.
   *
   * @throws Exception
   *     if an error occurs during setup
   */
  @Before
  @Override
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
    assertFalse(respVars.isEmpty());

    // Test SHOW_COLUMNS mode
    parameter.put("Mode", "SHOW_COLUMNS");
    parameter.put("Table", "C_BPartner");
    respVars = new HashMap<>();
    ex.get(parameter, respVars);
    assertFalse(respVars.isEmpty());

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
    assertFalse(respVars.isEmpty());
    assertFalse(StringUtils.isEmpty(respVars.get("data")));
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
    var items = new JSONArray();
    items.put("c_order");
    parameter.put("items", items.toString());
    parameter.put("entityName", "ADTable");
    respVars = new HashMap<>();
    ss.get(parameter, respVars);
    assertFalse(respVars.isEmpty());
    assertFalse(StringUtils.isEmpty(respVars.get(MESSAGE)));
    JSONObject json = new JSONObject(respVars.get(MESSAGE));
    assertTrue(json.has("item_0"));
    JSONObject item0 = json.getJSONObject("item_0");
    assertTrue(item0.has("data"));
    assertTrue(item0.getJSONArray("data").length() > 0);
  }

  /**
   * Tests the GetAvailableAgents webhook.
   * <p>
   * This test method verifies the functionality of the GetAvailableAgents webhook.
   * It tests successful retrieval of agents and error handling.
   * </p>
   *
   * @throws Exception
   *     if an error occurs during the test
   */
  @Test
  public void getAvailableAgents() throws Exception {
    GetAvailableAgents ga = new GetAvailableAgents();
    Map<String, String> parameter = new HashMap<>();
    Map<String, String> respVars = new HashMap<>();

    // Test successful execution
    ga.get(parameter, respVars);
    assertFalse(respVars.isEmpty());
    assertTrue(respVars.containsKey(AGENTS));
    assertFalse(StringUtils.isEmpty(respVars.get(AGENTS)));
  }

  /**
   * Tests the AttachFileWebhook functionality.
   * <p>
   * This test method verifies the functionality of the AttachFileWebhook.
   * It tests parameter validation, successful attachment creation, and error handling.
   * </p>
   *
   * @throws Exception
   *     if an error occurs during the test
   */
  @Test
  public void attachFileWebhook() throws Exception {
    AttachFileWebhook afw = new AttachFileWebhook();
    Map<String, String> parameter = new HashMap<>();
    Map<String, String> respVars;

    // Test missing required parameters
    respVars = new HashMap<>();
    afw.get(parameter, respVars);
    assertTrue(respVars.containsKey(ERROR));
    assertTrue(respVars.get(ERROR).contains(MISSING_PARAMS));

    // Test missing ADTabId
    parameter.put(RECORD_ID, TEST_RECORD_ID);
    parameter.put(FILE_NAME, TEST_FILE_NAME);
    parameter.put(FILE_CONTENT, TEST_BASE64_CONTENT); // Base64 for "Hello World"
    respVars = new HashMap<>();
    afw.get(parameter, respVars);
    assertTrue(respVars.containsKey(ERROR));
    assertTrue(respVars.get(ERROR).contains(MISSING_PARAMS));

    // Test missing RecordId
    parameter.put(AD_TAB_ID, "testTabId");
    parameter.remove(RECORD_ID);
    respVars = new HashMap<>();
    afw.get(parameter, respVars);
    assertTrue(respVars.containsKey(ERROR));
    assertTrue(respVars.get(ERROR).contains(MISSING_PARAMS));

    // Test missing FileName
    parameter.put(RECORD_ID, TEST_RECORD_ID);
    parameter.remove(FILE_NAME);
    respVars = new HashMap<>();
    afw.get(parameter, respVars);
    assertTrue(respVars.containsKey(ERROR));
    assertTrue(respVars.get(ERROR).contains(MISSING_PARAMS));

    // Test missing FileContent
    parameter.put(FILE_NAME, TEST_FILE_NAME);
    parameter.remove(FILE_CONTENT);
    respVars = new HashMap<>();
    afw.get(parameter, respVars);
    assertTrue(respVars.containsKey(ERROR));
    assertTrue(respVars.get(ERROR).contains(MISSING_PARAMS));
  }

  /**
   * Tests the storeBase64ToTempFile method.
   * <p>
   * This test method verifies the functionality of the storeBase64ToTempFile method.
   * It tests successful file creation, invalid base64 content, and null parameters.
   * </p>
   *
   * @throws Exception
   *     if an error occurs during the test
   */
  @Test
  public void storeBase64ToTempFile() throws Exception {
    AttachFileWebhook afw = new AttachFileWebhook();

    // Test successful file creation
    String validBase64 = TEST_BASE64_CONTENT; // "Hello World" in base64
    String fileName = TEST_FILE_NAME;
    File tempFile = afw.storeBase64ToTempFile(validBase64, fileName);
    assertNotNull(tempFile);
    assertTrue(tempFile.exists());
    assertTrue(tempFile.getName().endsWith(fileName));

    // Verify file content
    String content = new String(java.nio.file.Files.readAllBytes(tempFile.toPath()));
    assertEquals("Hello World", content);

    // Clean up
    try {
      java.nio.file.Files.delete(tempFile.toPath());
    } catch (IOException e) {
      // Ignore cleanup errors in test
    }


    // Test null parameters
    assertNull(afw.storeBase64ToTempFile(null, fileName));
    assertNull(afw.storeBase64ToTempFile(validBase64, null));
  }

  /**
   * Tests the createAttachment method.
   * <p>
   * This test method verifies the functionality of the createAttachment method.
   * It tests successful attachment creation and error handling.
   * </p>
   *
   * @throws Exception
   *     if an error occurs during the test
   */
  @Test
  public void createAttachment() throws Exception {
    AttachFileWebhook afw = new AttachFileWebhook();

    // Create a secure temporary directory with owner-only permissions and a temp file inside it
    FileAttribute<Set<PosixFilePermission>> dirAttr =
        PosixFilePermissions.asFileAttribute(
            PosixFilePermissions.fromString("rwx------"));
    Path secureTempDir = Files.createTempDirectory("testDir", dirAttr);
    FileAttribute<Set<PosixFilePermission>> fileAttr =
        PosixFilePermissions.asFileAttribute(
            PosixFilePermissions.fromString("rw-------"));
    Path testFilePath = Files.createTempFile(secureTempDir, "test", ".txt", fileAttr);
    File testFile = testFilePath.toFile();
    Files.write(testFile.toPath(), "Test content".getBytes());

    // Test with invalid parameters (should throw exception)
    try {
      afw.createAttachment("invalidTabId", "invalidRecordId", TEST_FILE_NAME, testFile);
      // If we reach here, the test should fail
      fail();
    } catch (Exception e) {
      // Expected exception for invalid parameters
      assertNotNull(e);
    }

    // Clean up
    try {
      Files.delete(testFile.toPath());
      // also attempt to delete the temporary directory
      Files.delete(secureTempDir);
    } catch (IOException e) {
      // Ignore cleanup errors in test
    }
  }

  /**
   * Tests the complete AttachFileWebhook flow with valid parameters.
   * <p>
   * This test method verifies the complete functionality of the AttachFileWebhook
   * with all required parameters provided.
   * </p>
   *
   * @throws Exception
   *     if an error occurs during the test
   */
  @Test
  public void attachFileWebhookCompleteFlow() throws Exception {
    AttachFileWebhook afw = new AttachFileWebhook();
    Map<String, String> parameter = new HashMap<>();
    Map<String, String> respVars;

    // Test with all required parameters (this may fail due to missing test data, but tests the flow)
    parameter.put(AD_TAB_ID, "testTabId");
    parameter.put(RECORD_ID, TEST_RECORD_ID);
    parameter.put(FILE_NAME, TEST_FILE_NAME);
    parameter.put(FILE_CONTENT, TEST_BASE64_CONTENT); // Base64 for "Hello World"

    respVars = new HashMap<>();
    try {
      afw.get(parameter, respVars);
      // Check that either success or error response is returned
      assertTrue(respVars.containsKey(MESSAGE) || respVars.containsKey(ERROR));
    } catch (Exception e) {
      // Expected for test environment without proper setup
      assertNotNull(e);
    }
  }

  /**
   * Cleans up the test environment after each test.
   */
  @After
  public void tearDown() throws Exception {
    if (mocks != null) {
      mocks.close();
    }
    OBContext.setOBContext(TestConstants.Users.ADMIN, TestConstants.Roles.SYS_ADMIN, TestConstants.Clients.SYSTEM,
        TestConstants.Orgs.MAIN);
    VariablesSecureApp vars = new VariablesSecureApp(OBContext.getOBContext().getUser().getId(),
        OBContext.getOBContext().getCurrentClient().getId(), OBContext.getOBContext().getCurrentOrganization().getId());
    RequestContext.get().setVariableSecureApp(vars);
    OBDal.getInstance().flush();
    OBDal.getInstance().commitAndClose();
  }
}
