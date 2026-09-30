"use client";

import { MutableRefObject, useEffect, useRef } from "react";
import maplibregl, { GeoJSONSource, Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { CLASS_COLOR, MapPayload, classGlyph } from "@/types/domain";
import { circlePolygon, haversineM } from "@/lib/geo";

const OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_FR = "https://a.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png";
const OSM_ATTR = "© OpenStreetMap contributors";

const CONF_STROKE: Record<string, string> = {
  HIGH: "#e8eef2",
  MEDIUM: "#7ecfc4",
  LOW: "#c9a227",
  UNRESOLVED: "#8a93a0",
};

interface Props {
  data: MapPayload | null;
  selectedId?: string | null;
  onSelect: (id: string) => void;
  layers: {
    observations: boolean;
    clusters: boolean;
    facilities: boolean;
    associationRing: boolean;
    selectedFootprint: boolean;
  };
  basemap: "osm" | "graphite";
}

export function IntelligenceMap({ data, selectedId, onSelect, layers, basemap }: Props) {
  const container = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const onSelectRef = useRef(onSelect);
  const lastFly = useRef<string | null>(null);
  const stateRef = useRef({ data, selectedId, layers, basemap });
  onSelectRef.current = onSelect;
  stateRef.current = { data, selectedId, layers, basemap };

  useEffect(() => {
    if (!container.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: {
        version: 8,
        glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
        sources: {
          osm: { type: "raster", tiles: [OSM], tileSize: 256, attribution: OSM_ATTR },
          graphite: {
            type: "raster",
            tiles: [OSM_FR],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors, tiles © OpenStreetMap France",
          },
        },
        layers: [
          { id: "osm", type: "raster", source: "osm" },
          { id: "graphite", type: "raster", source: "graphite", layout: { visibility: "none" } },
        ],
      },
      center: [78.9, 22.5],
      zoom: 4.6,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
    const onReady = () => applyIntelligenceMap(map, onSelectRef, stateRef, lastFly);
    map.on("load", onReady);
    if (map.isStyleLoaded()) onReady();
    mapRef.current = map;
    const ro = new ResizeObserver(() => map.resize());
    ro.observe(container.current);
    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (map) applyIntelligenceMap(map, onSelectRef, stateRef, lastFly);
  }, [data, layers, selectedId, basemap]);

  return <div ref={container} className="h-full w-full" />;
}

type MapState = {
  data: MapPayload | null;
  selectedId?: string | null;
  layers: Props["layers"];
  basemap: Props["basemap"];
};

const overlayHandlers = new WeakSet<MapLibreMap>();

function setLayerVisibility(map: MapLibreMap, layerId: string, visible: boolean) {
  if (!map.getLayer(layerId)) return;
  map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
}

function addLayerIfMissing(map: MapLibreMap, layer: Parameters<MapLibreMap["addLayer"]>[0]) {
  if (!map.getLayer(layer.id)) map.addLayer(layer);
}

function ensureOverlayLayers(map: MapLibreMap, onSelectRef: MutableRefObject<(id: string) => void>) {
  if (!map.getSource("observations")) {
    map.addSource("observations", {
      type: "geojson",
      data: emptyFc(),
      cluster: true,
      clusterMaxZoom: 9,
      clusterRadius: 44,
    });
  }
  if (!map.getSource("selected-footprint")) {
    map.addSource("selected-footprint", { type: "geojson", data: emptyFc() });
  }
  if (!map.getSource("association-ring")) {
    map.addSource("association-ring", { type: "geojson", data: emptyFc() });
  }
  if (!map.getSource("clusters")) {
    map.addSource("clusters", { type: "geojson", data: emptyFc() });
  }
  if (!map.getSource("nearby-facilities")) {
    map.addSource("nearby-facilities", { type: "geojson", data: emptyFc() });
  }
  addLayerIfMissing(map, {
    id: "obs-clusters",
    type: "circle",
    source: "observations",
    filter: ["has", "point_count"],
    paint: {
      "circle-color": "#6d7c89",
      "circle-radius": ["step", ["get", "point_count"], 11, 8, 15, 25, 20],
      "circle-opacity": 0.75,
      "circle-stroke-width": 1,
      "circle-stroke-color": "#0b0d10",
    },
  });
  addLayerIfMissing(map, {
    id: "obs-unclustered",
    type: "circle",
    source: "observations",
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-radius": 3,
      "circle-color": "#c5d0d8",
      "circle-opacity": 0.7,
    },
  });
  addLayerIfMissing(map, {
    id: "footprints",
    type: "circle",
    source: "selected-footprint",
    paint: {
      "circle-radius": 11,
      "circle-color": "#5fb3a8",
      "circle-opacity": 0.12,
      "circle-stroke-width": 1,
      "circle-stroke-color": "#7ecfc4",
      "circle-stroke-opacity": 0.55,
    },
  });
  addLayerIfMissing(map, {
    id: "association-fill",
    type: "fill",
    source: "association-ring",
    paint: { "fill-color": "#7ecfc4", "fill-opacity": 0.08 },
  });
  addLayerIfMissing(map, {
    id: "association-line",
    type: "line",
    source: "association-ring",
    paint: { "line-color": "#7ecfc4", "line-width": 1.2, "line-dasharray": [2, 2], "line-opacity": 0.85 },
  });
  addLayerIfMissing(map, {
    id: "cluster-fill",
    type: "circle",
    source: "clusters",
    paint: {
      "circle-radius": ["case", ["==", ["get", "selected"], 1], 9, 6],
      "circle-color": ["get", "color"],
      "circle-stroke-width": ["case", ["==", ["get", "selected"], 1], 2.4, 1.2],
      "circle-stroke-color": ["get", "confidenceStroke"],
    },
  });
  addLayerIfMissing(map, {
    id: "facility-mark",
    type: "circle",
    source: "nearby-facilities",
    paint: {
      "circle-radius": 5,
      "circle-color": "#7ecfc4",
      "circle-stroke-width": 1.5,
      "circle-stroke-color": "#0b0d10",
    },
  });
  if (overlayHandlers.has(map)) return;
  overlayHandlers.add(map);
  map.on("click", "cluster-fill", (e) => {
    const id = e.features?.[0]?.properties?.id;
    if (id) onSelectRef.current(String(id));
  });
  map.on("click", "obs-clusters", (e) => {
    const feature = e.features?.[0];
    if (!feature || feature.geometry.type !== "Point") return;
    const src = map.getSource("observations") as GeoJSONSource;
    void src.getClusterExpansionZoom(Number(feature.properties?.cluster_id)).then((zoom) => {
      const geom = feature.geometry as GeoJSON.Point;
      map.easeTo({ center: geom.coordinates as [number, number], zoom });
    });
  });
  map.on("mouseenter", "cluster-fill", () => {
    map.getCanvas().style.cursor = "pointer";
  });
  map.on("mouseleave", "cluster-fill", () => {
    map.getCanvas().style.cursor = "";
  });
}

function applyIntelligenceMap(
  map: MapLibreMap,
  onSelectRef: MutableRefObject<(id: string) => void>,
  stateRef: MutableRefObject<MapState>,
  lastFly: MutableRefObject<string | null>,
) {
  if (!map.isStyleLoaded()) return;
  ensureOverlayLayers(map, onSelectRef);
  const { data, selectedId, layers, basemap } = stateRef.current;
  setLayerVisibility(map, "osm", basemap === "osm");
  setLayerVisibility(map, "graphite", basemap === "graphite");
  if (!data) return;
  const obsFc = {
    type: "FeatureCollection" as const,
    features: data.observations.map((o) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [o.lon, o.lat] },
      properties: { id: o.id, cluster_id: o.cluster_id },
    })),
  };
  const clusterFc = {
    type: "FeatureCollection" as const,
    features: data.clusters.map((c) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [c.lon, c.lat] },
      properties: {
        id: c.id,
        color: CLASS_COLOR[c.label] || "#8a93a0",
        glyph: classGlyph(c.label),
        selected: c.id === selectedId ? 1 : 0,
        confidenceStroke: CONF_STROKE[c.confidence] || "#8a93a0",
      },
    })),
  };
  const selected = data.clusters.find((c) => c.id === selectedId);
  const footprintFc = {
    type: "FeatureCollection" as const,
    features: selected
      ? data.observations
          .filter((o) => o.cluster_id === selected.id)
          .map((o) => ({
            type: "Feature" as const,
            geometry: { type: "Point" as const, coordinates: [o.lon, o.lat] },
            properties: { id: o.id },
          }))
      : [],
  };
  const ringFc = {
    type: "FeatureCollection" as const,
    features:
      selected && layers.associationRing
        ? [
            {
              type: "Feature" as const,
              geometry: circlePolygon(selected.lon, selected.lat, 1000),
              properties: { note: "1 km spatial-association window, not a facility boundary" },
            },
          ]
        : [],
  };
  const nearby = selected
    ? data.facilities.filter((f) => haversineM(selected.lat, selected.lon, f.latitude, f.longitude) <= 5000)
    : [];
  const facFc = {
    type: "FeatureCollection" as const,
    features: (layers.facilities ? nearby : []).map((f) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [f.longitude, f.latitude] },
      properties: { id: f.id, name: f.name },
    })),
  };
  setSrc(map, "observations", obsFc);
  setSrc(map, "clusters", clusterFc);
  setSrc(map, "selected-footprint", footprintFc);
  setSrc(map, "association-ring", ringFc);
  setSrc(map, "nearby-facilities", facFc);
  setLayerVisibility(map, "obs-clusters", layers.observations);
  setLayerVisibility(map, "obs-unclustered", layers.observations);
  setLayerVisibility(map, "cluster-fill", layers.clusters);
  setLayerVisibility(map, "footprints", Boolean(layers.selectedFootprint && selected));
  setLayerVisibility(map, "association-fill", Boolean(layers.associationRing && selected));
  setLayerVisibility(map, "association-line", Boolean(layers.associationRing && selected));
  setLayerVisibility(map, "facility-mark", Boolean(layers.facilities && selected));
  if (selectedId && lastFly.current !== selectedId) {
    lastFly.current = selectedId;
    if (selected) map.easeTo({ center: [selected.lon, selected.lat], zoom: Math.max(map.getZoom(), 7.4), duration: 700 });
  }
}

function emptyFc() {
  return { type: "FeatureCollection" as const, features: [] };
}

function setSrc(map: MapLibreMap, id: string, data: GeoJSON.GeoJSON) {
  const src = map.getSource(id) as GeoJSONSource | undefined;
  src?.setData(data);
}
