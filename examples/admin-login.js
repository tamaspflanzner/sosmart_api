const API_BASE =
  process.env.API_BASE || "https://sosmart-api-staging-3kvj2tijtq-ew.a.run.app";

async function main() {
  const loginRes = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email: "demo-admin-staging@example.com",
      password: "DemoAdmin123!",
    }),
  });

  if (!loginRes.ok) {
    throw new Error(`Admin login failed: ${loginRes.status} ${await loginRes.text()}`);
  }

  const { access_token } = await loginRes.json();

  const meRes = await fetch(`${API_BASE}/api/v1/users/me`, {
    headers: {
      Authorization: `Bearer ${access_token}`,
    },
  });

  if (!meRes.ok) {
    throw new Error(`Protected API call failed: ${meRes.status} ${await meRes.text()}`);
  }

  const me = await meRes.json();
  console.log("Admin profile:");
  console.log(JSON.stringify(me, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
