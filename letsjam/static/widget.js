/**
 * letsjam – traffic simulation widget
 *
 * Reads from anywidget model:
 *   map_data   (object)  – nodes, streets, decorations, car_types, car_length, truck_length
 *   trajectory (Uint8Array / DataView source) – packed binary blob
 *   n_frames   (int)
 *   n_cars     (int)
 *
 * PIXI is defined by widget.py, which prepends pixi.min.js wrapped in an IIFE
 * that forces the CommonJS path and assigns the exports object to `const PIXI`.
 * No CDN loading, no globalThis magic needed here.
 */

// ---------------------------------------------------------------------------
// Binary trajectory parser
// ---------------------------------------------------------------------------
function parseTrajectory(buffer, nFrames, nCars) {
  const view = new DataView(
    buffer instanceof ArrayBuffer ? buffer : buffer.buffer
  );
  // header is still present in the blob
  const storedFrames = view.getInt32(0, true);
  const storedCars = view.getInt32(4, true);
  const frames = storedFrames || nFrames;
  const cars = storedCars || nCars;

  const edge_ids = new Int32Array(frames * cars);
  const dists = new Float32Array(frames * cars);

  let offset = 8;
  for (let f = 0; f < frames; f++) {
    for (let c = 0; c < cars; c++) {
      const idx = f * cars + c;
      edge_ids[idx] = view.getInt32(offset, true);
      dists[idx] = view.getFloat32(offset + 4, true);
      offset += 8;
    }
  }
  return { edge_ids, dists, n_frames: frames, n_cars: cars };
}

// ---------------------------------------------------------------------------
// Geometry helpers
// ---------------------------------------------------------------------------
function edgeWorldPos(nodes, streets, edgeId, dist) {
  const [fi, ti] = streets[edgeId];
  const [fx, fy] = nodes[fi];
  const [tx, ty] = nodes[ti];
  const len = Math.hypot(tx - fx, ty - fy);
  const t = len > 0 ? dist / len : 0;
  return {
    x: fx + (tx - fx) * t,
    y: fy + (ty - fy) * t,
    angle: Math.atan2(ty - fy, tx - fx),
  };
}

function lerp(a, b, t) { return a + (b - a) * t; }

function lerpAngle(a, b, t) {
  let diff = b - a;
  while (diff > Math.PI) diff -= 2 * Math.PI;
  while (diff < -Math.PI) diff += 2 * Math.PI;
  return a + diff * t;
}

// ---------------------------------------------------------------------------
// Colour palette
// ---------------------------------------------------------------------------
const COLORS = {
  background: 0x1a1a2e,
  street: 0x374151,
  streetLine: 0x4b5563,
  crossing: 0x4b5563,
  crossingRim: 0x6b7280,
  car: 0x60a5fa,
  truck: 0xfbbf24,
  parkFill: 0x15803d,
  parkBorder: 0x166534,
  riverFill: 0x3b82f6,
};

const HOUSE_COLORS = [0xf5d98b, 0xf0c96a, 0xefc14a, 0xf2d070, 0xf8e4a0, 0xf0b84a, 0xfad688, 0xeab84e];

const CROSSING_R = 5;
const CAR_WIDTH = 3;
const STOP_DISTANCE = 8;   // must match propagate.py stop_distance
const STOP_LINE_COLOR_RED   = 0xef4444;
const STOP_LINE_COLOR_GREEN = 0x4ade80;

// ---------------------------------------------------------------------------
// Traffic-light helpers
// ---------------------------------------------------------------------------

/** Parse the binary lights blob produced by Trajectory.lights_to_bytes(). */
function parseLights(buffer) {
  if (!buffer || buffer.byteLength < 8) return null;
  const buf = buffer instanceof ArrayBuffer ? buffer : buffer.buffer;
  const view = new DataView(buf);
  const n_frames = view.getInt32(0, true);
  const n_nodes  = view.getInt32(4, true);
  const data = new Int8Array(buf, 8, n_frames * n_nodes);
  return { data, n_frames, n_nodes };
}

/** Build inbound[node] = [street_id, ...] in the same order as Python's _build_graph. */
function buildInbound(nodes, streets) {
  const inbound = nodes.map(() => []);
  for (let s = 0; s < streets.length; s++) {
    inbound[streets[s][1]].push(s);
  }
  return inbound;
}

/** Redraw all stop lines for the given (possibly fractional) frame. */
function updateStopLines(g, mapData, inbound, lightsData, fracFrame) {
  g.clear();
  if (!lightsData) return;
  const { nodes, streets } = mapData;
  const STREET_WIDTH = mapData.car_length * 1.5;
  const { data, n_nodes } = lightsData;
  const frame = Math.min(Math.floor(fracFrame), lightsData.n_frames - 1);

  for (let s = 0; s < streets.length; s++) {
    const ti = streets[s][1];
    if (inbound[ti].length === 0) continue;   // source node — no light

    const [fi] = streets[s];
    const [fx, fy] = nodes[fi];
    const [tx, ty] = nodes[ti];
    const len = Math.hypot(tx - fx, ty - fy);
    if (len <= STOP_DISTANCE) continue;

    const t  = (len - STOP_DISTANCE) / len;
    const mx = fx + (tx - fx) * t;
    const my = fy + (ty - fy) * t;

    const dx = (tx - fx) / len;     // unit direction along street
    const dy = (ty - fy) / len;
    const px = -dy;                  // perpendicular (left of travel)
    const py =  dx;
    const hw = STREET_WIDTH / 2 + 1;

    const greenIdx   = data[frame * n_nodes + ti];
    const inboundIdx = inbound[ti].indexOf(s);
    const isGreen    = (greenIdx === inboundIdx);

    if (isGreen) {
      // filled triangle pointing toward the intersection
      g.lineStyle(0);
      g.beginFill(STOP_LINE_COLOR_GREEN, 0.9);
      g.drawPolygon([
        mx - px * hw, my - py * hw,   // base left
        mx + px * hw, my + py * hw,   // base right
        mx + dx * hw, my + dy * hw,   // tip (forward)
      ]);
      g.endFill();
    } else {
      // red line across the street
      g.lineStyle(1.5, STOP_LINE_COLOR_RED, 0.9);
      g.moveTo(mx - px * hw, my - py * hw);
      g.lineTo(mx + px * hw, my + py * hw);
    }
  }
}

// ---------------------------------------------------------------------------
// Decoration mesh helpers
// ---------------------------------------------------------------------------
const MESH_CELL = 8; // triangle grid cell size in world units

function pointInPolygon(px, py, pts) {
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const xi = pts[i][0], yi = pts[i][1];
    const xj = pts[j][0], yj = pts[j][1];
    if ((yi > py) !== (yj > py) &&
        px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

function randomShade(baseColor, range) {
  const f = (Math.random() - 0.5) * range;
  const r = (baseColor >> 16) & 0xff;
  const g = (baseColor >>  8) & 0xff;
  const b =  baseColor        & 0xff;
  const blend = (c) => Math.min(255, Math.max(0,
    f > 0 ? Math.round(c + (255 - c) * f) : Math.round(c * (1 + f))
  ));
  return (blend(r) << 16) | (blend(g) << 8) | blend(b);
}

function drawParkMesh(parent, pts) {
  const container = new PIXI.Container();
  parent.addChild(container);

  // Mask to clip triangles to the polygon boundary
  const mask = new PIXI.Graphics();
  mask.beginFill(0xffffff);
  mask.drawPolygon(pts.flat());
  mask.endFill();
  container.addChild(mask);
  container.mask = mask;

  const g = new PIXI.Graphics();
  container.addChild(g);

  const xs = pts.map(p => p[0]);
  const ys = pts.map(p => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);

  const cell = MESH_CELL * 2;
  for (let x = minX; x < maxX; x += cell) {
    for (let y = minY; y < maxY; y += cell) {
      const x1 = x + cell, y1 = y + cell;
      const tris = [
        [x, y,   x1, y,   x,  y1],
        [x1, y,  x1, y1,  x,  y1],
      ];
      for (const tri of tris) {
        g.lineStyle(0);
        g.beginFill(randomShade(COLORS.parkFill, 0.2), 1);
        g.drawPolygon(tri);
        g.endFill();
      }
    }
  }

}

// Catmull-Rom spline through pts ([x,y] array).
// Endpoints extended by mirroring the adjacent segment.
function catmullRomSpline(pts, samplesPerSegment = 10) {
  if (pts.length < 2) return pts.slice();
  const ext = [
    [2*pts[0][0] - pts[1][0],               2*pts[0][1] - pts[1][1]],
    ...pts,
    [2*pts[pts.length-1][0] - pts[pts.length-2][0],
     2*pts[pts.length-1][1] - pts[pts.length-2][1]],
  ];
  const result = [];
  for (let i = 1; i < ext.length - 2; i++) {
    const [p0, p1, p2, p3] = [ext[i-1], ext[i], ext[i+1], ext[i+2]];
    for (let s = 0; s < samplesPerSegment; s++) {
      const t = s / samplesPerSegment, t2 = t*t, t3 = t2*t;
      result.push([
        0.5*((2*p1[0]) + (-p0[0]+p2[0])*t + (2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2 + (-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3),
        0.5*((2*p1[1]) + (-p0[1]+p2[1])*t + (2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2 + (-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3),
      ]);
    }
  }
  result.push([...pts[pts.length-1]]);
  return result;
}

// Buffer a polyline by halfWidth; returns flat [x,y,...] closed polygon.
function bufferPolyline(pts, halfWidth) {
  const n = pts.length;
  const left = [], right = [];
  for (let i = 0; i < n; i++) {
    let nx, ny;
    if (i === 0) {
      const dx = pts[1][0]-pts[0][0], dy = pts[1][1]-pts[0][1];
      const l = Math.hypot(dx, dy) || 1;
      nx = -dy/l; ny = dx/l;
    } else if (i === n-1) {
      const dx = pts[n-1][0]-pts[n-2][0], dy = pts[n-1][1]-pts[n-2][1];
      const l = Math.hypot(dx, dy) || 1;
      nx = -dy/l; ny = dx/l;
    } else {
      const dx0 = pts[i][0]-pts[i-1][0], dy0 = pts[i][1]-pts[i-1][1];
      const l0 = Math.hypot(dx0, dy0) || 1;
      const dx1 = pts[i+1][0]-pts[i][0], dy1 = pts[i+1][1]-pts[i][1];
      const l1 = Math.hypot(dx1, dy1) || 1;
      nx = -dy0/l0 + -dy1/l1;
      ny =  dx0/l0 +  dx1/l1;
      const nl = Math.hypot(nx, ny) || 1;
      nx /= nl; ny /= nl;
    }
    left.push( [pts[i][0] + nx*halfWidth, pts[i][1] + ny*halfWidth]);
    right.push([pts[i][0] - nx*halfWidth, pts[i][1] - ny*halfWidth]);
  }
  const poly = [];
  for (const p of left)                        poly.push(p[0], p[1]);
  for (let i = right.length-1; i >= 0; i--)   poly.push(right[i][0], right[i][1]);
  return poly;
}

// ---------------------------------------------------------------------------
// House placement
// ---------------------------------------------------------------------------

function placeHouses(mapData) {
  const { nodes, streets, decorations, car_length } = mapData;
  const SW = car_length * 1.5;                 // street width

  const HW_MIN = car_length * 0.6,  HW_MAX = car_length * 1.3;   // house length range
  const HD_MIN = car_length * 0.45, HD_MAX = car_length * 0.85;   // house depth range
  const GAP = car_length * 0.4;               // gap from street edge to house edge
  const INTERVAL_MIN = car_length * 1.4;      // minimum spacing between house starts
  const INTERVAL_MAX = car_length * 3.2;      // maximum spacing
  const CLEARANCE = car_length * 0.2;         // extra buffer between houses
  // Worst-case bounding radius for collision checks
  const houseR = Math.hypot(HW_MAX, HD_MAX) / 2 + CLEARANCE;

  const parks = (decorations || []).filter(d => d.type === 'park').map(d => d.points);
  const rivers = (decorations || []).filter(d => d.type === 'river');

  function inAnyPark(x, y) {
    return parks.some(poly => pointInPolygon(x, y, poly));
  }

  function nearAnyRiver(x, y) {
    for (const river of rivers) {
      const pts = river.points;
      const minDist = (river.width ?? 8) / 2 + GAP + HD_MAX / 2;
      for (let i = 0; i < pts.length - 1; i++) {
        const [ax, ay] = pts[i], [bx, by] = pts[i + 1];
        const rdx = bx - ax, rdy = by - ay;
        const len2 = rdx * rdx + rdy * rdy;
        if (len2 === 0) continue;
        const t = Math.max(0, Math.min(1, ((x - ax) * rdx + (y - ay) * rdy) / len2));
        if (Math.hypot(x - (ax + t * rdx), y - (ay + t * rdy)) < minDist) return true;
      }
    }
    return false;
  }

  const placed = [];

  function canPlace(x, y) {
    if (inAnyPark(x, y)) return false;
    if (nearAnyRiver(x, y)) return false;
    return placed.every(h => Math.hypot(x - h.x, y - h.y) >= houseR * 2);
  }

  const houses = [];
  const margin = car_length * 1.5;  // keep clear of intersections

  for (const [fi, ti] of streets) {
    const [fx, fy] = nodes[fi];
    const [tx, ty] = nodes[ti];
    const sdx = tx - fx, sdy = ty - fy;
    const len = Math.hypot(sdx, sdy);
    if (len < margin * 2 + INTERVAL_MIN) continue;

    const ux = sdx / len, uy = sdy / len;   // unit along street
    const px = -uy, py = ux;                 // unit perpendicular (left)
    const angle = Math.atan2(sdy, sdx);

    let t = margin + Math.random() * INTERVAL_MIN;

    while (t < len - margin) {
      for (const side of [1, -1]) {
        const hw = HW_MIN + Math.random() * (HW_MAX - HW_MIN);
        const hd = HD_MIN + Math.random() * (HD_MAX - HD_MIN);
        const offset = SW / 2 + GAP + hd / 2;

        const hx = fx + ux * t + px * offset * side;
        const hy = fy + uy * t + py * offset * side;

        if (!canPlace(hx, hy)) continue;

        // Check all 4 corners against parks and rivers
        const corners = [
          [hx + ux * (hw / 2) + px * (hd / 2), hy + uy * (hw / 2) + py * (hd / 2)],
          [hx - ux * (hw / 2) + px * (hd / 2), hy - uy * (hw / 2) + py * (hd / 2)],
          [hx + ux * (hw / 2) - px * (hd / 2), hy + uy * (hw / 2) - py * (hd / 2)],
          [hx - ux * (hw / 2) - px * (hd / 2), hy - uy * (hw / 2) - py * (hd / 2)],
        ];
        if (corners.some(([cx, cy]) => inAnyPark(cx, cy) || nearAnyRiver(cx, cy))) continue;

        placed.push({ x: hx, y: hy });
        houses.push({
          x: hx, y: hy, w: hw, d: hd, angle,
          color: HOUSE_COLORS[Math.floor(Math.random() * HOUSE_COLORS.length)],
        });
      }
      t += INTERVAL_MIN + Math.random() * (INTERVAL_MAX - INTERVAL_MIN);
    }
  }

  return houses;
}

function drawHouses(parent, houses) {
  if (houses.length === 0) return;
  const g = new PIXI.Graphics();
  parent.addChild(g);

  for (const h of houses) {
    const hw = h.w / 2, hd = h.d / 2;
    const cos = Math.cos(h.angle), sin = Math.sin(h.angle);
    // Rotate corners from local space (x=along street, y=perpendicular) to world
    const pts = [
      [ hw * cos - hd * sin,  hw * sin + hd * cos],
      [-hw * cos - hd * sin, -hw * sin + hd * cos],
      [-hw * cos + hd * sin, -hw * sin - hd * cos],
      [ hw * cos + hd * sin,  hw * sin - hd * cos],
    ].flatMap(([ox, oy]) => [h.x + ox, h.y + oy]);

    g.lineStyle(0.5, 0x000000, 0.25);
    g.beginFill(h.color, 1);
    g.drawPolygon(pts);
    g.endFill();
  }
}

function drawRiverMesh(parent, pts, width, bgPadding) {
  const hw = (width ?? 8) / 2;
  const smooth = catmullRomSpline(pts, 10);
  const poly   = bufferPolyline(smooth, hw);

  // Background clearing strip so forests don't touch rivers
  if (bgPadding) {
    const bgPoly = bufferPolyline(smooth, hw + bgPadding);
    const bg = new PIXI.Graphics();
    bg.lineStyle(0);
    bg.beginFill(COLORS.background, 1);
    bg.drawPolygon(bgPoly);
    bg.endFill();
    parent.addChild(bg);
  }

  const container = new PIXI.Container();
  parent.addChild(container);

  const mask = new PIXI.Graphics();
  mask.beginFill(0xffffff);
  mask.drawPolygon(poly);
  mask.endFill();
  container.addChild(mask);
  container.mask = mask;

  const g = new PIXI.Graphics();
  container.addChild(g);

  const xs = [], ys = [];
  for (let i = 0; i < poly.length; i += 2) { xs.push(poly[i]); ys.push(poly[i+1]); }
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);

  for (let x = minX; x < maxX; x += MESH_CELL) {
    for (let y = minY; y < maxY; y += MESH_CELL) {
      const x1 = x + MESH_CELL, y1 = y + MESH_CELL;
      const tris = [
        [x, y,  x1, y,  x,  y1],
        [x1, y, x1, y1, x,  y1],
      ];
      for (const tri of tris) {
        g.lineStyle(0);
        g.beginFill(randomShade(COLORS.riverFill, 0.4), 1);
        g.drawPolygon(tri);
        g.endFill();
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Dashed center line (scaled to car_length)
// ---------------------------------------------------------------------------
function drawDashedCenterLine(g, fx, fy, tx, ty, car_length) {
  const dashLen = car_length * 0.7;
  const gapLen  = car_length * 0.5;
  const dx = tx - fx, dy = ty - fy;
  const len = Math.hypot(dx, dy);
  if (len < dashLen * 2) return;
  const ux = dx / len, uy = dy / len;
  g.lineStyle(0.8, 0xffffff, 0.45, 0.5);
  let d = gapLen;
  while (d + dashLen < len - gapLen) {
    g.moveTo(fx + ux * d,              fy + uy * d);
    g.lineTo(fx + ux * (d + dashLen),  fy + uy * (d + dashLen));
    d += dashLen + gapLen;
  }
}

// ---------------------------------------------------------------------------
// Zebra crossings at both ends of every street
// ---------------------------------------------------------------------------
function drawZebraCrossings(g, nodes, streets, car_length) {
  const SW       = car_length * 1.5;
  const strW     = car_length * 0.15;   // stripe width across road
  const strG     = car_length * 0.15;   // gap between stripes
  const N        = 4;
  const totalLat = N * strW + (N - 1) * strG;
  const startLat = -totalLat / 2;
  const offset   = CROSSING_R + car_length * 0.05;
  const hl       = SW / 2;              // half-length along road direction

  for (const [fi, ti] of streets) {
    const [fx, fy] = nodes[fi];
    const [tx, ty] = nodes[ti];
    const dx = tx - fx, dy = ty - fy;
    const len = Math.hypot(dx, dy);
    if (len < offset * 2 + car_length) continue;

    const ux = dx / len, uy = dy / len;
    const px = -uy, py = ux;

    for (const [nx, ny, sign] of [[fx, fy, 1], [tx, ty, -1]]) {
      // Base position: offset from node along road direction
      const bx = nx + ux * offset * sign;
      const by = ny + uy * offset * sign;
      for (let k = 0; k < N; k++) {
        const lat = startLat + k * (strW + strG) + strW / 2;
        const cx  = bx + px * lat;
        const cy  = by + py * lat;
        const hs  = strW / 2;
        g.lineStyle(0);
        g.beginFill(0xffffff, 0.75);
        g.drawPolygon([
          cx + ux * hl + px * hs, cy + uy * hl + py * hs,
          cx - ux * hl + px * hs, cy - uy * hl + py * hs,
          cx - ux * hl - px * hs, cy - uy * hl - py * hs,
          cx + ux * hl - px * hs, cy + uy * hl - py * hs,
        ]);
        g.endFill();
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Scene builder
// ---------------------------------------------------------------------------
function buildStaticScene(parent, mapData) {
  const { nodes, streets, decorations } = mapData;

  // Parks first, then rivers on top of parks
  for (const dec of (decorations || [])) {
    if (dec.type === "park") drawParkMesh(parent, dec.points);
  }
  for (const dec of (decorations || [])) {
    if (dec.type === "river") drawRiverMesh(parent, dec.points, dec.width, mapData.car_length * 0.25);
  }

  // Houses sit between green areas and streets
  drawHouses(parent, placeHouses(mapData));

  const STREET_WIDTH = mapData.car_length * 1.5;
  const BG_STREET_WIDTH = STREET_WIDTH + mapData.car_length;  // wider clearing strip
  const BG_CROSSING_R = BG_STREET_WIDTH / 2;

  const g = new PIXI.Graphics();
  parent.addChild(g);

  // Background clearing strips so terrain doesn't touch streets
  for (let i = 0; i < streets.length; i++) {
    const [fi, ti] = streets[i];
    const [fx, fy] = nodes[fi];
    const [tx, ty] = nodes[ti];
    g.lineStyle(BG_STREET_WIDTH, COLORS.background, 1, 0.5);
    g.moveTo(fx, fy);
    g.lineTo(tx, ty);
  }

  // Background circles at crossings
  for (const [x, y] of nodes) {
    g.lineStyle(0);
    g.beginFill(COLORS.background, 1);
    g.drawCircle(x, y, BG_CROSSING_R);
    g.endFill();
  }

  // Actual streets on top of clearing layer
  for (let i = 0; i < streets.length; i++) {
    const [fi, ti] = streets[i];
    const [fx, fy] = nodes[fi];
    const [tx, ty] = nodes[ti];
    g.lineStyle(STREET_WIDTH, COLORS.street, 1, 0.5);
    g.moveTo(fx, fy);
    g.lineTo(tx, ty);
    drawDashedCenterLine(g, fx, fy, tx, ty, mapData.car_length);
  }

  drawZebraCrossings(g, nodes, streets, mapData.car_length);

  for (const [x, y] of nodes) {
    g.lineStyle(0.5, COLORS.crossingRim, 0.9);
    g.beginFill(COLORS.crossing, 1);
    const octPts = [];
    for (let k = 0; k < 8; k++) {
      const a = (k * Math.PI * 2) / 8 + Math.PI / 8;
      octPts.push(x + Math.cos(a) * CROSSING_R, y + Math.sin(a) * CROSSING_R);
    }
    g.drawPolygon(octPts);
    g.endFill();
  }

  return g;
}

// ---------------------------------------------------------------------------
// World outline
// ---------------------------------------------------------------------------
function buildWorldOutline(parent, mapData) {
  const mapW = mapData.width;
  const mapH = mapW * 9 / 16;
  const g = new PIXI.Graphics();
  //g.lineStyle(2, 0xffdd00, 1);
  g.drawRect(0, -mapH / 2, mapW, mapH);
  parent.addChild(g);
  return g;
}

// ---------------------------------------------------------------------------
// Car sprites
// ---------------------------------------------------------------------------
function buildCarSprites(parent, mapData) {
  const { car_types, car_length, truck_length } = mapData;
  const container = new PIXI.Container();
  parent.addChild(container);
  const sprites = [];

  for (let i = 0; i < car_types.length; i++) {
    const isTruck = car_types[i] === 1;
    const length = isTruck ? truck_length : car_length;
    const color = isTruck ? COLORS.truck : COLORS.car;
    const g = new PIXI.Graphics();
    g.beginFill(color, 1);
    g.drawRoundedRect(-length / 2, -CAR_WIDTH / 2, length, CAR_WIDTH, 1);
    g.endFill();
    g.lineStyle(0.5, 0xffffff, 0.25);
    g.drawRoundedRect(-length / 2, -CAR_WIDTH / 2, length, CAR_WIDTH, 1);
    g.visible = false;
    container.addChild(g);
    sprites.push(g);
  }
  return sprites;
}

// ---------------------------------------------------------------------------
// Per-frame render
// ---------------------------------------------------------------------------
function renderFrame(traj, mapData, sprites, fracFrame) {
  const { nodes, streets } = mapData;
  const { edge_ids, dists, n_frames, n_cars } = traj;
  const f0 = Math.floor(fracFrame);
  const f1 = Math.min(f0 + 1, n_frames - 1);
  const t = fracFrame - f0;

  for (let c = 0; c < n_cars; c++) {
    const g = sprites[c];
    const eid0 = edge_ids[f0 * n_cars + c];
    const eid1 = edge_ids[f1 * n_cars + c];

    if (eid0 === -1) { g.visible = false; continue; }
    g.visible = true;

    const d0 = dists[f0 * n_cars + c];
    const d1 = dists[f1 * n_cars + c];
    let x, y, angle;

    if (eid0 === eid1 || eid1 === -1) {
      const d = eid1 === -1 ? d0 : lerp(d0, d1, t);
      const pos = edgeWorldPos(nodes, streets, eid0, d);
      x = pos.x; y = pos.y; angle = pos.angle;
    } else {
      const p0 = edgeWorldPos(nodes, streets, eid0, d0);
      const p1 = edgeWorldPos(nodes, streets, eid1, d1);
      x = lerp(p0.x, p1.x, t);
      y = lerp(p0.y, p1.y, t);
      angle = lerpAngle(p0.angle, p1.angle, t);
    }
    g.x = x; g.y = y; g.rotation = angle;
  }
}

// ---------------------------------------------------------------------------
// anywidget entry point
// ---------------------------------------------------------------------------
export async function render({ model, el }) {
  // --- guard: surface errors visibly instead of silently failing -----------
  function showError(err) {
    el.innerHTML = `<div style="color:#f87171;font-family:monospace;padding:8px;background:#1a1a2e;border-radius:4px;">
      <b>letsjam error</b><br><pre style="margin:4px 0;white-space:pre-wrap">${err}</pre>
    </div>`;
    console.error("[letsjam]", err);
  }

  if (typeof PIXI === "undefined" || !PIXI.Application) {
    showError(
      `PIXI not loaded (typeof PIXI = "${typeof PIXI}", ` +
      `PIXI.Application = "${typeof PIXI !== "undefined" ? PIXI.Application : "n/a"}"). ` +
      `Check the browser console for a PixiJS init error.`
    );
    return;
  }

  // --- DOM skeleton --------------------------------------------------------
  el.innerHTML = "";
  el.classList.add("letsjam-widget");

  const canvasWrap = document.createElement("div");
  canvasWrap.className = "letsjam-canvas-wrap";
  el.appendChild(canvasWrap);

  const controls = document.createElement("div");
  controls.className = "letsjam-controls";
  el.appendChild(controls);

  const playBtn = document.createElement("button");
  playBtn.className = "letsjam-btn";
  playBtn.textContent = "Play";
  controls.appendChild(playBtn);

  const replayBtn = document.createElement("button");
  replayBtn.className = "letsjam-btn";
  replayBtn.textContent = "Replay";
  controls.appendChild(replayBtn);

  const speedWrap = document.createElement("div");
  speedWrap.className = "letsjam-speed-wrap";
  speedWrap.innerHTML =
    "<span>slow</span>" +
    '<input type="range" class="letsjam-speed" min="0.2" max="30" step="0.1" value="8">' +
    "<span>fast</span>";
  controls.appendChild(speedWrap);

  const frameLabel = document.createElement("span");
  frameLabel.className = "letsjam-frame-label";
  controls.appendChild(frameLabel);

  // --- PixiJS app ----------------------------------------------------------
  const CANVAS_W = 960;
  const CANVAS_H = Math.round(CANVAS_W * 9 / 16); // 540 — fixed 16:9

  let app;
  try {
    app = new PIXI.Application({
      width: CANVAS_W,
      height: CANVAS_H,
      backgroundColor: COLORS.background,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
    });
  } catch (e) {
    showError("PIXI.Application init failed:\n" + e);
    return;
  }
  canvasWrap.appendChild(app.view);

  // --- state ---------------------------------------------------------------
  let traj = null;
  let sprites = [];
  let stopLineGfx = null;
  let lightsData = null;
  let inbound = [];
  let playing = false;
  let fracFrame = 0;
  let lastTs = null;
  let rafId = null;
  const speedSlider = speedWrap.querySelector(".letsjam-speed");

  // --- playback loop -------------------------------------------------------
  function loop(ts) {
    rafId = requestAnimationFrame(loop);
    if (!traj || !playing) { lastTs = null; return; }
    if (lastTs !== null) {
      const dt = (ts - lastTs) / 1000;
      const fps = parseFloat(speedSlider.value);
      fracFrame += dt * fps;
      if (fracFrame >= traj.n_frames - 1) {
        fracFrame = traj.n_frames - 1;
        playing = false;
        playBtn.textContent = "Play";
      }
    }
    lastTs = ts;
    const mapData = model.get("map_data");
    updateStopLines(stopLineGfx, mapData, inbound, lightsData, fracFrame);
    renderFrame(traj, mapData, sprites, fracFrame);
    frameLabel.textContent = `frame ${Math.min(Math.floor(fracFrame) + 1, traj.n_frames)} / ${traj.n_frames}`;
    app.renderer.render(app.stage);
  }
  rafId = requestAnimationFrame(loop);

  // --- controls ------------------------------------------------------------
  playBtn.addEventListener("click", () => {
    if (!traj) return;
    if (fracFrame >= traj.n_frames - 1) fracFrame = 0;
    playing = !playing;
    playBtn.textContent = playing ? "Pause" : "Play";
  });

  replayBtn.addEventListener("click", () => {
    if (!traj) return;
    fracFrame = 0;
    playing = true;
    playBtn.textContent = "Pause";
  });

  el.tabIndex = 0;
  el.addEventListener("keydown", (e) => {
    if (!traj) return;
    if (e.key === "ArrowRight") {
      playing = false; fracFrame = Math.min(fracFrame + 1, traj.n_frames - 1);
      playBtn.textContent = "Play";
    } else if (e.key === "ArrowLeft") {
      playing = false; fracFrame = Math.max(fracFrame - 1, 0);
      playBtn.textContent = "Play";
    }
  });

  // --- model change handlers -----------------------------------------------
  function rebuildScene() {
    try {
      const mapData = model.get("map_data");
      const rawTraj = model.get("trajectory");
      if (!mapData || !rawTraj || rawTraj.byteLength === 0) return;

      app.stage.removeChildren();
      sprites = [];
      playing = false;
      fracFrame = 0;
      playBtn.textContent = "Play";

      // Keep the renderer at the fixed display resolution so the framebuffer
      // is never smaller than the canvas element.  Scale the world container
      // so that map coordinates fill the display exactly.
      const mapW = mapData.width;
      const mapH = mapW * 9 / 16;
      const scale = CANVAS_W / mapW;

      const world = new PIXI.Container();
      world.scale.set(scale);
      world.x = 0;
      world.y = CANVAS_H / 2;   // world y=0 at canvas vertical centre
      app.stage.addChild(world);

      buildStaticScene(world, mapData);

      stopLineGfx = new PIXI.Graphics();
      world.addChild(stopLineGfx);

      buildWorldOutline(world, mapData);
      sprites = buildCarSprites(world, mapData);

      inbound = buildInbound(mapData.nodes, mapData.streets);
      lightsData = parseLights(model.get("lights"));

      traj = parseTrajectory(rawTraj, model.get("n_frames") || 0, model.get("n_cars") || 0);
      updateStopLines(stopLineGfx, mapData, inbound, lightsData, 0);
      renderFrame(traj, mapData, sprites, 0);
      frameLabel.textContent = `frame 1 / ${traj.n_frames}`;
      app.renderer.render(app.stage);
    } catch (e) {
      showError("Scene build failed:\n" + e.stack || e);
    }
  }

  model.on("change:map_data", rebuildScene);
  model.on("change:trajectory", rebuildScene);
  model.on("change:lights", rebuildScene);
  rebuildScene();

  return () => {
    cancelAnimationFrame(rafId);
    app.destroy(true, { children: true });
  };
}
