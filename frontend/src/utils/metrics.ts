import type { ServerState, WorldState } from "../types";

export function isIncident(server: ServerState) {
  return server.temp > 80 || server.error_rate > 5 || server.health < 60;
}

export function getFleetStats(state: WorldState) {
  const servers = Object.values(state.servers);
  const count = servers.length || 1;

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
    avgLoad: totals.load / count,
    avgTemp: totals.temp / count,
    avgHealth: totals.health / count,
    avgError: totals.error / count,
    totalPower: totals.power,
    coolingCount: totals.cooling,
    serverCount: count
  };
}
