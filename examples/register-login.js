const API_BASE =
  process.env.API_BASE || "https://sosmart-api-staging-3kvj2tijtq-ew.a.run.app";

async function main() {
  const email = `example-user-${Date.now()}@example.com`;
  const password = "StrongPass123!";

  const registerRes = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      full_name: "Example User",
      password,
    }),
  });

  if (!registerRes.ok) {
    throw new Error(`Register failed: ${registerRes.status} ${await registerRes.text()}`);
  }

  const registeredUser = await registerRes.json();
  console.log("Registered user:");
  console.log(JSON.stringify(registeredUser, null, 2));

  const loginRes = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      password,
    }),
  });

  if (!loginRes.ok) {
    throw new Error(`Login failed: ${loginRes.status} ${await loginRes.text()}`);
  }

  const { access_token } = await loginRes.json();

  const statsRes = await fetch(`${API_BASE}/api/v1/stats/me`, {
    headers: {
      Authorization: `Bearer ${access_token}`,
    },
  });

  if (!statsRes.ok) {
    throw new Error(`Protected API call failed: ${statsRes.status} ${await statsRes.text()}`);
  }

  const stats = await statsRes.json();
  console.log("My stats:");
  console.log(JSON.stringify(stats, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
