package com.etendoerp.copilot.toolpack.tools;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Properties;

import javax.mail.Authenticator;
import javax.mail.Message;
import javax.mail.PasswordAuthentication;
import javax.mail.Session;
import javax.mail.Transport;
import javax.mail.internet.InternetAddress;
import javax.mail.internet.MimeMessage;

import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;

import org.codehaus.jettison.json.JSONObject;

import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import com.etendoerp.copilot.toolpack.tools.support.ToolSecrets;

import dev.langchain4j.agent.tool.ToolSpecification;
import dev.langchain4j.model.chat.request.json.JsonObjectSchema;
import dev.langchain4j.model.chat.request.json.JsonRawSchema;

/** Sends mail through the configured legacy provider. */
@ApplicationScoped @Named("SendEmailTool")
public class SendEmailTool implements ServerTool {
  private static final String DESCRIPTION = " This tool sends an email using the SMTP method or the Resend method.\n    It is very important not to omit information, because the email is sent to another person and\n    the information must be clear and concise, and not summarized.\n    ";
  private static final HttpClient HTTP = HttpClient.newHttpClient();

  @Override public String name() { return "SendEmailTool"; }
  @Override public ToolSpecification specification() {
    return ToolSpecification.builder().name(name()).description(DESCRIPTION).parameters(JsonObjectSchema.builder()
        .addProperty("subject", JsonRawSchema.from("{\"type\":\"string\",\"description\":\"Subject of the email\"}"))
        .addProperty("mailto", JsonRawSchema.from("{\"type\":\"string\",\"description\":\"Email address of the recipient\"}"))
        .addProperty("html", JsonRawSchema.from("{\"type\":\"string\",\"description\":\"HTML content of the email\"}"))
        .required(java.util.Arrays.asList("subject", "mailto", "html")).build()).build();
  }

  @Override public String execute(JSONObject args, ToolExecutionContext ctx) throws Exception {
    String subject = required(args, "subject");
    String to = required(args, "mailto");
    String html = required(args, "html");
    String method = ToolSecrets.get("mail.method");
    if (method == null) method = "SMTP";
    if ("resend".equals(method)) {
      String key = ToolSecrets.get("resend.api.key");
      if (key == null) throw new IllegalStateException("Resend API key is not configured (resend.api.key)");
      JSONObject payload = new JSONObject();
      payload.put("from", "onboarding@resend.dev");
      payload.put("to", new org.codehaus.jettison.json.JSONArray().put(to));
      payload.put("subject", "[Copilot Tool Test]:" + subject);
      payload.put("html", html);
      HttpRequest request = HttpRequest.newBuilder(URI.create("https://api.resend.com/emails"))
          .timeout(Duration.ofSeconds(60)).header("Authorization", "Bearer " + key)
          .header("Content-Type", "application/json")
          .POST(HttpRequest.BodyPublishers.ofString(payload.toString())).build();
      HttpResponse<String> response = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
      if (response.statusCode() < 200 || response.statusCode() >= 300) {
        throw new IllegalStateException("Email sending failed: " + response.body());
      }
      return "{\"message\":\"Mail sent successfully\"}";
    }
    if ("SMTP".equals(method)) {
      String from = ToolSecrets.get("mail.from");
      String password = ToolSecrets.get("smtp.password");
      if (from == null) throw new IllegalStateException("SMTP sender is not configured (mail.from)");
      if (password == null) throw new IllegalStateException("SMTP password is not configured (smtp.password)");
      Properties properties = new Properties();
      properties.setProperty("mail.smtp.host", "smtp.gmail.com");
      properties.setProperty("mail.smtp.port", "587");
      properties.setProperty("mail.smtp.starttls.enable", "true");
      properties.setProperty("mail.smtp.auth", "true");
      Session session = Session.getInstance(properties, new Authenticator() {
        @Override protected PasswordAuthentication getPasswordAuthentication() {
          return new PasswordAuthentication(from, password);
        }
      });
      MimeMessage message = new MimeMessage(session);
      message.setFrom(new InternetAddress(from));
      message.setRecipients(Message.RecipientType.TO, InternetAddress.parse(to));
      message.setSubject(subject);
      message.setContent(html, "text/html; charset=UTF-8");
      Transport.send(message);
      return "{\"message\":\"Mail sent successfully\"}";
    }
    return "{\"message\":\"Mail method not supported\"}";
  }

  private static String required(JSONObject args, String name) {
    String value = args.optString(name, null);
    if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " is required");
    return value;
  }
}
