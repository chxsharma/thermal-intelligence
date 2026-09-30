export function circlePolygon(lon: number, lat: number, radiusM: number, steps = 48): GeoJSON.Polygon {
  const coords: [number, number][] = [];
  const latR = (lat * Math.PI) / 180;
  const mPerDegLat = 111320;
  const mPerDegLon = 111320 * Math.cos(latR);
  for (let i = 0; i <= steps; i += 1) {
    const t = (2 * Math.PI * i) / steps;
    coords.push([lon + (radiusM * Math.cos(t)) / mPerDegLon, lat + (radiusM * Math.sin(t)) / mPerDegLat]);
  }
  return { type: "Polygon", coordinates: [coords] };
}

export function haversineM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const r = 6371000;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dp = ((lat2 - lat1) * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.min(1, Math.sqrt(a)));
}
