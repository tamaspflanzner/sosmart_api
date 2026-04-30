const API_BASE =
  process.env.API_BASE || "https://sosmart-api-staging-3kvj2tijtq-ew.a.run.app";

async function loginAsDemoUser() {
  const loginRes = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email: "demo-user-staging@example.com",
      password: "DemoUser123!",
    }),
  });

  if (!loginRes.ok) {
    throw new Error(`Demo user login failed: ${loginRes.status} ${await loginRes.text()}`);
  }

  return loginRes.json();
}

async function main() {
  const { access_token } = await loginAsDemoUser();

  const tripPayload = {
    trip_id: `example-trip-${Date.now()}`,
    purpose: "school",
    begin_time: "2026-04-30T09:00:00Z",
    end_time: "2026-04-30T09:25:00Z",
    legs: [
      {
        origin: "Home",
        destination: "Bus Stop",
        transport_mode: "walking",
        distance_km: 0.6,
        co2_emission_kg: 0.0,
        co2_saved_kg: 0.115,
        begin_time: "2026-04-30T09:00:00Z",
        end_time: "2026-04-30T09:08:00Z",
      },
      {
        origin: "Bus Stop",
        destination: "School",
        transport_mode: "bus",
        distance_km: 4.8,
        co2_emission_kg: 0.394,
        co2_saved_kg: 0.528,
        begin_time: "2026-04-30T09:08:00Z",
        end_time: "2026-04-30T09:25:00Z",
      },
    ],
  };

  const createTripRes = await fetch(`${API_BASE}/api/v1/trips`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${access_token}`,
    },
    body: JSON.stringify(tripPayload),
  });

  if (!createTripRes.ok) {
    throw new Error(`Trip creation failed: ${createTripRes.status} ${await createTripRes.text()}`);
  }

  const createdTrip = await createTripRes.json();
  console.log("Created trip:");
  console.log(JSON.stringify(createdTrip, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
