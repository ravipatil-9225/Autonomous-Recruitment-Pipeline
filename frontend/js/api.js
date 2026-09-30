/**
 * Autonomous Recruitment Pipeline (ARP) — API Client
 * Seamlessly interfaces with FastAPI REST endpoints and WebSocket stream.
 * Includes deterministic mock fallback for offline dev/presentation mode.
 */

class ARPApiClient {
  constructor() {
    this.baseUrl = window.location.origin.includes(':8000') 
      ? '/api/v1' 
      : 'http://localhost:8000/api/v1';
    this.token = localStorage.getItem('arp_jwt_token') || null;
    this.currentRole = localStorage.getItem('arp_user_role') || 'recruiter';
    this.useMockFallback = false;
  }

  setToken(token, role = 'recruiter') {
    this.token = token;
    this.currentRole = role;
    if (token) localStorage.setItem('arp_jwt_token', token);
    if (role) localStorage.setItem('arp_user_role', role);
  }

  getHeaders(isMultipart = false) {
    const headers = {};
    if (!isMultipart) {
      headers['Content-Type'] = 'application/json';
    }
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    return headers;
  }

  async request(endpoint, options = {}) {
    if (this.useMockFallback) {
      return this._handleMock(endpoint, options);
    }

    try {
      const url = `${this.baseUrl}${endpoint}`;
      const response = await fetch(url, {
        ...options,
        headers: {
          ...this.getHeaders(options.body instanceof FormData),
          ...(options.headers || {}),
        },
      });

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          console.warn(`Auth error on ${endpoint}: ${response.status}`);
        }
        const errData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(errData.detail || `Request failed with ${response.status}`);
      }

      return await response.json();
    } catch (err) {
      console.warn(`API Server unreachable or error at ${endpoint}. Activating Mock Engine:`, err.message);
      this.useMockFallback = true;
      return this._handleMock(endpoint, options);
    }
  }

  // ── Jobs Endpoints ────────────────────────────────────────────────────────
  async listJobs(status = null, page = 1, pageSize = 20) {
    const query = new URLSearchParams({ page, page_size: pageSize });
    if (status) query.append('status', status);
    return this.request(`/jobs?${query.toString()}`);
  }

  async createJob(jobData) {
    return this.request('/jobs', {
      method: 'POST',
      body: JSON.stringify(jobData),
    });
  }

  async getJob(jobId) {
    return this.request(`/jobs/${jobId}`);
  }

  async publishJob(jobId) {
    return this.request(`/jobs/${jobId}/publish`, { method: 'POST' });
  }

  async closeJob(jobId) {
    return this.request(`/jobs/${jobId}/close`, { method: 'POST' });
  }

  // ── Resumes Endpoints ──────────────────────────────────────────────────────
  async uploadResume(file, jobId = null) {
    const formData = new FormData();
    formData.append('file', file);
    if (jobId) formData.append('job_id', jobId);

    return this.request('/resumes/upload', {
      method: 'POST',
      body: formData,
    });
  }

  async deleteCandidate(candidateId) {
    return this.request(`/resumes/candidate/${candidateId}`, {
      method: 'DELETE',
    });
  }

  // ── Pipeline Endpoints ────────────────────────────────────────────────────
  async triggerPipeline(jobId, resumeIds = []) {
    return this.request('/pipeline/run', {
      method: 'POST',
      body: JSON.stringify({ job_id: jobId, resume_ids: resumeIds }),
    });
  }

  async getPipelineStatus(runId) {
    return this.request(`/pipeline/${runId}`);
  }

  async submitDecision(runId, decision, notes = '') {
    return this.request(`/pipeline/${runId}/decision`, {
      method: 'POST',
      body: JSON.stringify({ decision, notes }),
    });
  }

  // ── Live WebSocket Pipeline Stream ─────────────────────────────────────────
  connectPipelineWS(runId, onMessage, onError, onClose) {
    if (this.useMockFallback) {
      return this._simulatePipelineWS(runId, onMessage, onClose);
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.origin.includes(':8000') 
      ? window.location.host 
      : 'localhost:8000';
    const wsUrl = `${wsProtocol}//${wsHost}/ws/pipeline/${runId}`;

    try {
      const socket = new WebSocket(wsUrl);
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onMessage(data);
        } catch (e) {
          console.error('WS parse error', e);
        }
      };
      socket.onerror = (e) => onError && onError(e);
      socket.onclose = () => onClose && onClose();
      return socket;
    } catch (e) {
      console.warn('WS fallback to simulation mode');
      return this._simulatePipelineWS(runId, onMessage, onClose);
    }
  }

  // ── Realistic Enterprise Simulation Engine (for fallback) ───────────────────
  _handleMock(endpoint, options) {
    const method = options.method || 'GET';
    
    if (endpoint.startsWith('/jobs') && method === 'GET') {
      return {
        total: 3,
        page: 1,
        page_size: 20,
        pages: 1,
        items: [
          {
            id: 'd9b1a03e-8fa9-4089-a517-5e926a112001',
            title: 'Senior AI / Agent Systems Engineer',
            department: 'AI & Research',
            location: 'San Francisco, CA / Remote',
            status: 'open',
            created_at: new Date(Date.now() - 3600000 * 24 * 3).toISOString(),
          },
          {
            id: 'c8f2b14f-7ea8-4190-b628-6f037b223112',
            title: 'Staff Distributed Backend Architect (Python/Go)',
            department: 'Core Infrastructure',
            location: 'New York, NY / Hybrid',
            status: 'open',
            created_at: new Date(Date.now() - 3600000 * 24 * 6).toISOString(),
          },
          {
            id: 'b7e3a25e-6fb7-4201-c739-7a148c334223',
            title: 'Machine Learning Infrastructure Tech Lead',
            department: 'ML Platform',
            location: 'Seattle, WA',
            status: 'draft',
            created_at: new Date(Date.now() - 3600000 * 24 * 10).toISOString(),
          },
        ]
      };
    }

    if (endpoint === '/pipeline/run' && method === 'POST') {
      return {
        run_id: 'run-' + Math.random().toString(36).substring(2, 9),
        job_id: 'd9b1a03e-8fa9-4089-a517-5e926a112001',
        celery_task_id: 'celery-' + Math.random().toString(36).substring(2, 9),
        status: 'queued',
        created_at: new Date().toISOString(),
        message: 'Pipeline queued. Poll /api/v1/pipeline/{run_id} for status.',
      };
    }

    if (endpoint.includes('/resumes/candidate') && method === 'DELETE') {
      return {
        candidate_id: endpoint.split('/').pop(),
        pii_wiped: true,
        s3_files_deleted: 1,
        chroma_embeddings_deleted: 1,
        message: 'Candidate PII wiped successfully per GDPR right-to-deletion.',
      };
    }

    return { status: 'ok', mock: true };
  }

  _simulatePipelineWS(runId, onMessage, onClose) {
    const stages = [
      { status: 'running', activeNode: 'parser', summary: { stage: 'Resume Parsing & S3 De-identification', progress: 15 } },
      { status: 'running', activeNode: 'screener', summary: { stage: 'Vector Similarity & Experience Scoring', progress: 35 } },
      { status: 'running', activeNode: 'evaluator', summary: { stage: 'Evaluation Agent & Multi-criteria Ranking', progress: 60 } },
      { status: 'running', activeNode: 'bias_audit', summary: { stage: 'Four-Fifths Bias & Disparity Check', progress: 80 } },
      { status: 'running', activeNode: 'hitl', summary: { stage: 'Awaiting Recruiter Review & Decision', progress: 90 } },
      { status: 'completed', activeNode: 'completed', summary: { ranked: 5, shortlisted: 3, stage: 'Pipeline Complete' } },
    ];

    let step = 0;
    const interval = setInterval(() => {
      if (step < stages.length) {
        onMessage({
          run_id: runId,
          status: stages[step].status,
          activeNode: stages[step].activeNode,
          summary: stages[step].summary,
          timestamp: new Date().toISOString(),
        });
        step++;
      } else {
        clearInterval(interval);
        if (onClose) onClose();
      }
    }, 1800);

    return { close: () => clearInterval(interval) };
  }
}

export const api = new ARPApiClient();
