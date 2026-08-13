import fs from "node:fs";
import ELK from "elkjs/lib/elk.bundled.js";

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) throw new Error("usage: node elk_layout.mjs input.json output.json");
const input = JSON.parse(fs.readFileSync(inputPath, "utf8"));
const scalable = input.layout.mode === "scalable";
const graph = {
  id: "root",
  layoutOptions: {
    "elk.algorithm": "layered",
    "elk.direction": "RIGHT",
    "elk.edgeRouting": "ORTHOGONAL",
    "elk.partitioning.activate": "true",
    "elk.layered.layering.strategy": scalable ? "LONGEST_PATH" : "NETWORK_SIMPLEX",
    "elk.layered.crossingMinimization.strategy": scalable ? "NONE" : "LAYER_SWEEP",
    "elk.layered.crossingMinimization.greedySwitch.type": scalable ? "OFF" : "TWO_SIDED",
    "elk.layered.nodePlacement.strategy": scalable ? "LINEAR_SEGMENTS" : "BRANDES_KOEPF",
    "elk.layered.nodePlacement.bk.edgeStraightening": "IMPROVE_STRAIGHTNESS",
    "elk.layered.considerModelOrder.strategy": "PREFER_NODES",
    "elk.layered.highDegreeNodes.treatment": scalable ? "false" : "true",
    "elk.layered.highDegreeNodes.threshold": "16",
    "elk.layered.thoroughness": scalable ? "1" : "7",
    "elk.layered.mergeEdges": "false",
    "elk.spacing.nodeNode": String(input.layout.nodeSpacing),
    "elk.layered.spacing.nodeNodeBetweenLayers": String(input.layout.layerSpacing),
    "elk.layered.spacing.edgeNodeBetweenLayers": String(input.layout.edgeNodeSpacing),
    "elk.spacing.edgeEdge": String(input.layout.edgeSpacing),
    "elk.padding": `[top=${input.layout.margin},left=${input.layout.margin},bottom=${input.layout.margin},right=${input.layout.margin}]`,
    "elk.randomSeed": "1"
  },
  children: input.nodes.map(node => ({
    id: node.id,
    width: node.layoutWidth,
    height: node.height,
    layoutOptions: {
      "elk.portConstraints": "FIXED_POS",
      "elk.partitioning.partition": String(node.rank)
    },
    ports: node.ports.map(port => ({
      id: `${node.id}:${port.id}`,
      x: port.x,
      y: port.y,
      width: 0,
      height: 0,
      layoutOptions: { "elk.port.side": port.side }
    }))
  })),
  edges: input.edges.map(edge => ({
    id: edge.id,
    sources: [`${edge.source}:${edge.sourcePort}`],
    targets: [`${edge.target}:${edge.targetPort}`]
  }))
};

const started = performance.now();
const output = await new ELK().layout(graph);
const result = {
  runtimeMs: performance.now() - started,
  mode: scalable ? "scalable" : "quality",
  width: output.width,
  height: output.height,
  nodes: Object.fromEntries((output.children ?? []).map(node => [node.id, { x: node.x, y: node.y }])),
  edges: Object.fromEntries((output.edges ?? []).map(edge => {
    const sections = edge.sections ?? [];
    if (sections.length !== 1) throw new Error(`${edge.id}: expected one section, got ${sections.length}`);
    const section = sections[0];
    return [edge.id, { points: [section.startPoint, ...(section.bendPoints ?? []), section.endPoint] }];
  }))
};
fs.writeFileSync(outputPath, JSON.stringify(result));
