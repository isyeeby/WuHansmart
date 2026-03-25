import React, { useCallback, useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const WUHAN_CENTER: [number, number] = [30.5928, 114.3055];

const pinIcon = L.icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

function MapClickHandler({ onPick }: { onPick: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(e) {
      onPick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function RecenterOnCoords({ lat, lng }: { lat: number; lng: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView([lat, lng], Math.max(map.getZoom(), 15));
  }, [lat, lng, map]);
  return null;
}

export interface LocationMapPickerProps {
  latitude?: number | null;
  longitude?: number | null;
  onPick: (lat: number, lng: number) => void;
  height?: number;
}

/**
 * 地图点选经纬度：点击地图放置/移动标记；默认中心武汉。
 */
export const LocationMapPicker: React.FC<LocationMapPickerProps> = ({
  latitude,
  longitude,
  onPick,
  height = 220,
}) => {
  const hasPoint =
    latitude != null &&
    longitude != null &&
    !Number.isNaN(latitude) &&
    !Number.isNaN(longitude);

  const center = useMemo<[number, number]>(
    () => (hasPoint ? [latitude!, longitude!] : WUHAN_CENTER),
    [hasPoint, latitude, longitude]
  );

  const handlePick = useCallback(
    (lat: number, lng: number) => {
      onPick(Number(lat.toFixed(6)), Number(lng.toFixed(6)));
    },
    [onPick]
  );

  return (
    <div className="rounded-sm overflow-hidden border border-[#ebe7e0]">
      <MapContainer
        center={center}
        zoom={hasPoint ? 15 : 11}
        style={{ height, width: '100%' }}
        scrollWheelZoom
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapClickHandler onPick={handlePick} />
        {hasPoint && <RecenterOnCoords lat={latitude!} lng={longitude!} />}
        {hasPoint && <Marker position={[latitude!, longitude!]} icon={pinIcon} />}
      </MapContainer>
      <p className="text-xs text-[#888] px-2 py-1.5 bg-[#faf9f7]">
        点击地图即可设置房源坐标；也可先填地址再使用「解析地址」自动定位。
      </p>
    </div>
  );
};
