const http = require("http");

const question = process.argv[2] || "Who won Roland Garros last year?";
console.log("Q:", question);

const body = JSON.stringify({
  messages: [
    {
      role: "user",
      parts: [{ type: "text", text: question }],
    },
  ],
});

const req = http.request(
  {
    hostname: "localhost",
    port: 3000,
    path: "/api/chat",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    timeout: 60000,
  },
  (res) => {
    let data = "";
    console.log("Status:", res.statusCode);
    res.on("data", (chunk) => (data += chunk));
    res.on("end", () => {
      if (res.statusCode !== 200) {
        console.log("ERROR:", data.slice(0, 500));
        return;
      }
      const lines = data.split("\n").filter(Boolean);
      let fullText = "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6);
        if (payload === "[DONE]") break;
        try {
          const obj = JSON.parse(payload);
          if (obj.type === "text-delta") fullText += obj.delta;
          if (obj.type === "error") console.log("ERROR:", obj.errorText?.slice(0, 200));
          if (obj.type === "tool-input-available") console.log("[tool]", obj.toolName, JSON.stringify(obj.input));
        } catch {}
      }
      if (fullText) console.log("\nA:", fullText);
      console.log("--- done ---");
    });
  }
);
req.on("timeout", () => {
  console.log("TIMEOUT after 60s");
  req.destroy();
});
req.on("error", (e) => console.log("REQ ERROR:", e.message));
req.write(body);
req.end();
