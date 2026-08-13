const root = document.querySelector("#lane-flow");

const LANE_FLOW = {
  working: ["waiting"],
  waiting: ["done", "failed"],
  done: [],
  failed: [],
};

const LABELS = {
  working: "進行中",
  waiting: "判断待ち",
  done: "完了",
  failed: "失敗",
};

function laneNode(lane) {
  const node = document.createElement("span");
  node.className = "flow-node";
  node.dataset.lane = lane;
  node.textContent = LABELS[lane];
  return node;
}

function arrow(from, to) {
  const edge = document.createElement("span");
  edge.className = "flow-edge";
  edge.dataset.from = from;
  edge.dataset.to = to;
  edge.setAttribute("aria-hidden", "true");
  edge.textContent = "→";
  return edge;
}

function renderFlow() {
  root.replaceChildren();
  const primary = document.createElement("div");
  primary.className = "flow-primary";
  primary.append(laneNode("working"), arrow("working", "waiting"), laneNode("waiting"));

  const outcomes = document.createElement("div");
  outcomes.className = "flow-outcomes";
  for (const lane of LANE_FLOW.waiting) {
    const branch = document.createElement("span");
    branch.className = "flow-branch";
    branch.append(arrow("waiting", lane), laneNode(lane));
    outcomes.append(branch);
  }

  root.append(primary, outcomes);
}

renderFlow();
