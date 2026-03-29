import { useEffect, useMemo, useState } from "react";

import {
  createLoadBalancer,
  createLoadBalancersBatch,
  createProject,
  deleteLoadBalancer,
  deleteProject,
  listLoadBalancers,
  listNodes,
  listProjects,
  updateLoadBalancer,
  updateProject,
  type LoadBalancer,
  type Node,
  type Project
} from "../api/infrastructure";
import { formatDate, formatDateTime } from "../utils/format";

type DraftState = {
  name: string;
  description: string;
};

type BalancerType = "nginx" | "haproxy" | "traefik";

type BalancerDraft = {
  projectId: string;
  nodeIds: string[];
  type: BalancerType;
  listenPort: string;
};

const EMPTY_DRAFT: DraftState = {
  name: "",
  description: ""
};

const EMPTY_LB_DRAFT: BalancerDraft = {
  projectId: "",
  nodeIds: [],
  type: "nginx",
  listenPort: "80"
};

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [projectBalancers, setProjectBalancers] = useState<LoadBalancer[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [lbOpen, setLbOpen] = useState(false);
  const [createDraft, setCreateDraft] = useState<DraftState>(EMPTY_DRAFT);
  const [editDraft, setEditDraft] = useState<DraftState>(EMPTY_DRAFT);
  const [lbDraft, setLbDraft] = useState<BalancerDraft>(EMPTY_LB_DRAFT);
  const [editingLbId, setEditingLbId] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const [projectData, nodeData] = await Promise.all([listProjects(), listNodes()]);
      setProjects(Array.isArray(projectData.projects) ? projectData.projects : []);
      setNodes(Array.isArray(nodeData.nodes) ? nodeData.nodes : []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const filteredProjects = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return projects;
    return projects.filter((project) => {
      const hay = `${project.name} ${project.id} ${project.description ?? ""}`.toLowerCase();
      return hay.includes(needle);
    });
  }, [projects, query]);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId]
  );

  const nodeMap = useMemo(() => {
    const map = new Map<string, Node>();
    nodes.forEach((node) => map.set(node.id, node));
    return map;
  }, [nodes]);

  const loadProjectBalancers = async (projectId: string) => {
    const data = await listLoadBalancers({ projectId });
    setProjectBalancers(Array.isArray(data.loadBalancers) ? data.loadBalancers : []);
  };

  const openCreate = () => {
    setCreateDraft(EMPTY_DRAFT);
    setCreateOpen(true);
    setError(null);
  };

  const closeCreate = () => {
    setCreateOpen(false);
    setCreateDraft(EMPTY_DRAFT);
  };

  const openEdit = (project: Project) => {
    setSelectedProjectId(project.id);
    setEditDraft({
      name: project.name,
      description: project.description || ""
    });
    setEditOpen(true);
    setLbOpen(false);
    setError(null);
  };

  const closeEdit = () => {
    setEditOpen(false);
    setSelectedProjectId(null);
    setLbOpen(false);
  };

  const openLoadBalancerMenu = async () => {
    if (!selectedProject) return;
    setLbOpen(true);
    setEditingLbId(null);
    setLbDraft({ ...EMPTY_LB_DRAFT, projectId: selectedProject.id });
    await loadProjectBalancers(selectedProject.id);
  };

  const closeLoadBalancerMenu = () => {
    setLbOpen(false);
    setEditingLbId(null);
    setLbDraft(EMPTY_LB_DRAFT);
  };

  const toggleLbNode = (nodeId: string) => {
    setLbDraft((current) => ({
      ...current,
      nodeIds: current.nodeIds.includes(nodeId)
        ? current.nodeIds.filter((value) => value !== nodeId)
        : [...current.nodeIds, nodeId]
    }));
  };

  const startEditBalancer = (balancer: LoadBalancer) => {
    setEditingLbId(balancer.id);
    setLbDraft({
      projectId: balancer.projectId,
      nodeIds: [balancer.nodeId],
      type: balancer.type,
      listenPort: String(balancer.listenPort ?? 80)
    });
  };

  const resetBalancerDraft = () => {
    setEditingLbId(null);
    setLbDraft({ ...EMPTY_LB_DRAFT, projectId: selectedProject?.id || "" });
  };

  const createNewProject = async () => {
    if (!createDraft.name.trim()) {
      setError("Project name is required");
      return;
    }
    setSaving(true);
    try {
      await createProject({
        name: createDraft.name.trim(),
        description: createDraft.description.trim() || undefined
      });
      closeCreate();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setSaving(false);
    }
  };

  const saveProject = async () => {
    if (!selectedProject || !editDraft.name.trim()) {
      setError("Project name is required");
      return;
    }
    setSaving(true);
    try {
      await updateProject(selectedProject.id, {
        name: editDraft.name.trim(),
        description: editDraft.description.trim()
      });
      await refresh();
      closeEdit();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save project");
    } finally {
      setSaving(false);
    }
  };

  const removeProject = async () => {
    if (!selectedProject) return;
    setSaving(true);
    try {
      await deleteProject(selectedProject.id);
      await refresh();
      closeEdit();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete project");
    } finally {
      setSaving(false);
    }
  };

  const saveBalancer = async () => {
    if (!selectedProject) return;
    if (lbDraft.nodeIds.length === 0) {
      setError("Select at least one node");
      return;
    }
    setSaving(true);
    try {
      const port = Number.parseInt(lbDraft.listenPort, 10);
      if (editingLbId) {
        await updateLoadBalancer(editingLbId, {
          projectId: selectedProject.id,
          nodeId: lbDraft.nodeIds[0],
          type: lbDraft.type,
          listenPort: port,
          status: "running"
        });
      } else if (lbDraft.nodeIds.length === 1) {
        await createLoadBalancer({
          projectId: selectedProject.id,
          nodeId: lbDraft.nodeIds[0],
          type: lbDraft.type,
          listenPort: port
        });
      } else {
        await createLoadBalancersBatch({
          projectId: selectedProject.id,
          nodeIds: lbDraft.nodeIds,
          type: lbDraft.type,
          listenPort: port
        });
      }
      resetBalancerDraft();
      await loadProjectBalancers(selectedProject.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save load balancer");
    } finally {
      setSaving(false);
    }
  };

  const removeBalancer = async (balancerId: string) => {
    if (!selectedProject) return;
    setSaving(true);
    try {
      await deleteLoadBalancer(balancerId);
      await loadProjectBalancers(selectedProject.id);
      if (editingLbId === balancerId) resetBalancerDraft();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete load balancer");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-eyebrow">Ownership</div>
          <h2 className="page-title">Projects</h2>
        </div>
        <div className="page-actions">
          <div className="status-chip">Projects {projects.length}</div>
          <button type="button" className="button primary" onClick={openCreate}>
            Add project
          </button>
        </div>
      </div>

      {error ? (
        <div className="alert">
          <strong>Error:</strong> {error}
        </div>
      ) : null}

      <section className="card library-page-card">
        <div className="library-page-head">
          <div className="card-title">Project library</div>
        </div>

        <div className="fleet-search">
          <label htmlFor="projectSearch">Search</label>
          <input
            id="projectSearch"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="project name, id, description"
          />
        </div>

        {loading ? <div className="empty">Loading projects...</div> : null}
        {!loading && filteredProjects.length === 0 ? <div className="empty">No projects found.</div> : null}

        {!loading && filteredProjects.length > 0 ? (
          <div className="library-grid">
            {filteredProjects.map((project) => (
              <button key={project.id} type="button" className="library-card" onClick={() => openEdit(project)}>
                <div className="library-card-head">
                  <div className="library-card-title">{project.name}</div>
                  <span className="severity-badge severity-succeeded">{formatDate(project.createdAt)}</span>
                </div>
                <div className="library-card-meta">{project.id}</div>
                <div className="library-card-description">{project.description || "No description yet."}</div>
              </button>
            ))}
          </div>
        ) : null}
      </section>

      {createOpen ? (
        <div className="overlay-shell" role="presentation" onClick={closeCreate}>
          <div className="overlay-panel overlay-panel-narrow" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="overlay-head">
              <div className="card-title">Create project</div>
              <button type="button" className="button outline" onClick={closeCreate}>Close</button>
            </div>
            <div className="overlay-body">
              <div className="project-form">
                <div className="project-field">
                  <label htmlFor="projectCreateName">Name</label>
                  <input
                    id="projectCreateName"
                    value={createDraft.name}
                    onChange={(event) => setCreateDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Project name"
                  />
                </div>
                <div className="project-field">
                  <label htmlFor="projectCreateDescription">Description</label>
                  <textarea
                    id="projectCreateDescription"
                    rows={5}
                    value={createDraft.description}
                    onChange={(event) => setCreateDraft((current) => ({ ...current, description: event.target.value }))}
                    placeholder="Describe what this project owns or serves"
                  />
                </div>
                <div className="overlay-actions">
                  <div className="spacer" />
                  <button type="button" className="button primary" disabled={saving} onClick={createNewProject}>
                    {saving ? "Creating..." : "Create project"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {editOpen && selectedProject ? (
        <div className="overlay-shell" role="presentation" onClick={closeEdit}>
          <div className="overlay-panel" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="overlay-head">
              <div>
                <div className="card-title">Project editor</div>
              </div>
              <div className="operations-actions">
                <button type="button" className="button outline" onClick={openLoadBalancerMenu}>Load balancers</button>
                <button type="button" className="button outline" onClick={closeEdit}>Close</button>
              </div>
            </div>
            <div className="overlay-body">
              <div className="payload-grid">
                <div>
                  <div className="payload-label">Project ID</div>
                  <div className="fleet-mono">{selectedProject.id}</div>
                </div>
                <div>
                  <div className="payload-label">Created</div>
                  <div>{formatDateTime(selectedProject.createdAt)}</div>
                </div>
                <div>
                  <div className="payload-label">Updated</div>
                  <div>{formatDateTime(selectedProject.updatedAt)}</div>
                </div>
              </div>

              <div className="project-form">
                <div className="project-field">
                  <label htmlFor="projectEditName">Name</label>
                  <input
                    id="projectEditName"
                    value={editDraft.name}
                    onChange={(event) => setEditDraft((current) => ({ ...current, name: event.target.value }))}
                  />
                </div>
                <div className="project-field">
                  <label htmlFor="projectEditDescription">Description</label>
                  <textarea
                    id="projectEditDescription"
                    rows={6}
                    value={editDraft.description}
                    onChange={(event) => setEditDraft((current) => ({ ...current, description: event.target.value }))}
                  />
                </div>
                <div className="overlay-actions">
                  <button type="button" className="button outline" disabled={saving} onClick={removeProject}>Delete</button>
                  <div className="spacer" />
                  <button type="button" className="button primary" disabled={saving} onClick={saveProject}>
                    {saving ? "Saving..." : "Save changes"}
                  </button>
                </div>
              </div>

              {lbOpen ? (
                <section className="project-lb-panel">
                  <div className="operations-panel-head">
                    <div>
                      <div className="card-title">Load balancer nodes</div>
                      <div className="control-hint">Create, adjust, and remove load balancer nodes under this project.</div>
                    </div>
                    <button type="button" className="button outline" onClick={closeLoadBalancerMenu}>Close menu</button>
                  </div>

                  <div className="project-lb-form-grid">
                    <div className="project-field">
                      <label>Target nodes</label>
                      <div className="operations-v2-node-grid">
                        {nodes.map((node) => (
                          <label key={node.id} className={`operations-v2-node ${lbDraft.nodeIds.includes(node.id) ? "selected" : ""}`.trim()}>
                            <input
                              type="checkbox"
                              checked={lbDraft.nodeIds.includes(node.id)}
                              onChange={() => toggleLbNode(node.id)}
                              disabled={Boolean(editingLbId) && lbDraft.nodeIds[0] !== node.id && lbDraft.nodeIds.includes(node.id) === false}
                            />
                            <span>{node.hostname}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                    <div className="project-lb-inline-fields">
                      <div className="project-field">
                        <label htmlFor="lbType">Type</label>
                        <select id="lbType" value={lbDraft.type} onChange={(event) => setLbDraft((current) => ({ ...current, type: event.target.value as BalancerType }))}>
                          <option value="nginx">nginx</option>
                          <option value="haproxy">haproxy</option>
                          <option value="traefik">traefik</option>
                        </select>
                      </div>
                      <div className="project-field">
                        <label htmlFor="lbPort">Listen port</label>
                        <input id="lbPort" type="number" min={1} max={65535} value={lbDraft.listenPort} onChange={(event) => setLbDraft((current) => ({ ...current, listenPort: event.target.value }))} />
                      </div>
                    </div>
                    <div className="overlay-actions">
                      <button type="button" className="button outline" onClick={resetBalancerDraft}>Reset</button>
                      <div className="spacer" />
                      <button type="button" className="button primary" disabled={saving} onClick={saveBalancer}>
                        {saving ? "Saving..." : editingLbId ? "Update node" : "Create node"}
                      </button>
                    </div>
                  </div>

                  <div className="command-list">
                    {projectBalancers.length === 0 ? (
                      <div className="empty">No load balancer nodes for this project yet.</div>
                    ) : (
                      projectBalancers.map((balancer) => {
                        const node = nodeMap.get(balancer.nodeId);
                        return (
                          <div key={balancer.id} className="command-row" style={{ cursor: "default" }}>
                            <div className="command-row-main">
                              <div className="command-row-title">{balancer.type} · {balancer.listenPort ?? "-"}</div>
                              <div className="command-row-meta">{node?.hostname ?? balancer.nodeId}</div>
                            </div>
                            <div className="operations-actions">
                              <span className={`severity-badge severity-${balancer.status === "running" ? "succeeded" : "queued"}`}>{balancer.status}</span>
                              <button type="button" className="button outline" onClick={() => startEditBalancer(balancer)}>Adjust</button>
                              <button type="button" className="button outline" onClick={() => removeBalancer(balancer.id)}>Remove</button>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </section>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
