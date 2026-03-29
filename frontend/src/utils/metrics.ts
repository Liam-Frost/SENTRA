import type { ServerState, WorldState } from "../types";

export function isIncident(server: ServerState) {
  if (server.status === "thermal_shutdown") return true;
  if (server.status !== "running") return false;
  return (
    server.temp > 80 ||
    server.error_rate > 5 ||
    server.health < 60 ||
    server.load > 85
  );
}

export function getFleetStats(state: WorldState) {
  const servers = Object.values(state.servers);
  const count = servers.length;
  const divisor = count > 0 ? count : 1;

  const totals = servers.reduce(
    (acc, server) => {
      acc.load += server.load;
      acc.temp += server.temp;
      acc.health += server.health;
      acc.power += server.power;
      acc.error += server.error_rate;
      acc.cooling += server.cooling ? 1 : 0;
      return acc;
    },
    { load: 0, temp: 0, health: 0, power: 0, error: 0, cooling: 0 }
  );

  return {
    avgLoad: totals.load / divisor,
    avgTemp: totals.temp / divisor,
    avgHealth: totals.health / divisor,
    avgError: totals.error / divisor,
    totalPower: totals.power,
    coolingCount: totals.cooling,
    serverCount: count
  };
}
