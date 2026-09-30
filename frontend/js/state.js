/**
 * Autonomous Recruitment Pipeline (ARP) — State Store
 * Reactive application store with custom event listeners.
 */

class ARPState {
  constructor() {
    this.jobs = [];
    this.activeJobId = null;
    this.activeJob = null;
    this.candidates = [
      {
        id: 'cand-001',
        name: 'Dr. Elena Rostova',
        email: 'e.rostova@ai-research.org',
        phone: '+1 (555) 349-8821',
        role_applied: 'Senior AI / Agent Systems Engineer',
        years_exp: 7.5,
        skills: ['LangGraph', 'Multi-Agent LLMs', 'PyTorch', 'FastAPI', 'Distributed Systems'],
        scores: {
          similarity: 0.94,
          experience: 0.92,
          interview: 0.90,
          bias_penalty: 0.00,
          final: 0.924,
        },
        rank: 1,
        stage: 'shortlisted',
        recruiter_decision: null,
        notes: 'Top tier contributor with 4 peer-reviewed multi-agent papers.',
        interview_questions: [
          'How do you handle cyclic message loops in stateful multi-agent graphs?',
          'Describe how you implement checkpointing and rollback with LangGraph.',
          'Explain your strategy for rate-limiting concurrent LLM inference calls.'
        ]
      },
      {
        id: 'cand-002',
        name: 'Marcus Vance',
        email: 'mvance.dev@proton.me',
        phone: '+1 (555) 782-9014',
        role_applied: 'Senior AI / Agent Systems Engineer',
        years_exp: 6.0,
        skills: ['Python', 'LangChain', 'Celery', 'PostgreSQL', 'Docker', 'FastAPI'],
        scores: {
          similarity: 0.88,
          experience: 0.85,
          interview: 0.86,
          bias_penalty: 0.00,
          final: 0.864,
        },
        rank: 2,
        stage: 'shortlisted',
        recruiter_decision: null,
        notes: 'Strong backend infrastructure and workflow orchestration profile.',
        interview_questions: [
          'How do you design a scalable Celery queue architecture for bursty file ingestion?',
          'What are your primary techniques for AES PII encryption at rest in SQLAlchemy?'
        ]
      },
      {
        id: 'cand-003',
        name: 'Amina Al-Mansoor',
        email: 'amina.almansoor@eng.tech',
        phone: '+1 (555) 912-3341',
        role_applied: 'Senior AI / Agent Systems Engineer',
        years_exp: 5.0,
        skills: ['PyTorch', 'Transformer NLP', 'Vector Databases', 'Milvus', 'Python'],
        scores: {
          similarity: 0.84,
          experience: 0.80,
          interview: 0.82,
          bias_penalty: 0.00,
          final: 0.821,
        },
        rank: 3,
        stage: 'shortlisted',
        recruiter_decision: null,
        notes: 'Solid vector search and embedding indexing experience.',
        interview_questions: [
          'Compare HNSW vs IVF indexing in high-scale vector retrieval.',
          'How do you evaluate cross-encoder reranking vs bi-encoder embeddings?'
        ]
      },
      {
        id: 'cand-004',
        name: 'Devin Zhao',
        email: 'd.zhao@cloudsystems.io',
        phone: '+1 (555) 601-2299',
        role_applied: 'Senior AI / Agent Systems Engineer',
        years_exp: 3.5,
        skills: ['Python', 'Docker', 'Kubernetes', 'FastAPI', 'Redis'],
        scores: {
          similarity: 0.72,
          experience: 0.65,
          interview: 0.68,
          bias_penalty: 0.00,
          final: 0.685,
        },
        rank: 4,
        stage: 'screening',
        recruiter_decision: null,
        notes: 'Good DevOps foundation, junior in direct multi-agent AI.',
        interview_questions: [
          'What are the core differences between sync and async task scheduling?'
        ]
      }
    ];

    this.activeRun = {
      run_id: null,
      status: 'idle', // idle | running | completed | failed
      activeNode: null, // parser | screener | evaluator | bias_audit | hitl | completed
      progress: 0,
      logs: [],
    };

    this.metrics = {
      totalCandidates: 142,
      activeJobs: 3,
      avgMatchScore: 88.4,
      diversityParityScore: 0.94,
      queueLatencyMs: 18,
    };

    this.listeners = new Map();
  }

  subscribe(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
    return () => {
      const arr = this.listeners.get(event).filter(cb => cb !== callback);
      this.listeners.set(event, arr);
    };
  }

  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(cb => cb(data));
    }
  }

  setJobs(jobs) {
    this.jobs = jobs;
    if (jobs.length > 0 && !this.activeJobId) {
      this.setActiveJob(jobs[0].id);
    }
    this.emit('jobs:updated', this.jobs);
  }

  setActiveJob(jobId) {
    this.activeJobId = jobId;
    this.activeJob = this.jobs.find(j => j.id === jobId) || null;
    this.emit('job:selected', this.activeJob);
  }

  updatePipelineStatus(statusUpdate) {
    this.activeRun = {
      ...this.activeRun,
      ...statusUpdate,
    };
    if (statusUpdate.summary?.stage) {
      this.activeRun.logs.push({
        time: new Date().toLocaleTimeString(),
        stage: statusUpdate.summary.stage,
        node: statusUpdate.activeNode || 'system',
      });
    }
    this.emit('pipeline:updated', this.activeRun);
  }

  recordCandidateDecision(candidateId, decision, notes) {
    const candidate = this.candidates.find(c => c.id === candidateId);
    if (candidate) {
      candidate.recruiter_decision = decision;
      candidate.stage = decision === 'hire' ? 'hired' : 'rejected';
      if (notes) candidate.notes = notes;
      this.emit('candidates:updated', this.candidates);
    }
  }

  removeCandidate(candidateId) {
    this.candidates = this.candidates.filter(c => c.id !== candidateId);
    this.emit('candidates:updated', this.candidates);
  }

  addResume(parsedResume) {
    // Add new candidate entry
    const newCand = {
      id: parsedResume.candidate_id || 'cand-' + Math.random().toString(36).substring(2, 6),
      name: parsedResume.name || 'New Upload Candidate',
      email: parsedResume.email || 'encrypted-pii@arp.corp',
      phone: parsedResume.phone || '+1 (555) 000-0000',
      role_applied: this.activeJob?.title || 'Applied Position',
      years_exp: parsedResume.years_exp || 4.0,
      skills: parsedResume.skills || ['Python', 'FastAPI', 'Machine Learning'],
      scores: {
        similarity: 0.81,
        experience: 0.79,
        interview: 0.80,
        bias_penalty: 0.00,
        final: 0.801,
      },
      rank: this.candidates.length + 1,
      stage: 'screening',
      recruiter_decision: null,
      notes: 'Ingested via Celery background parsing pipeline.',
      interview_questions: ['Describe your core workflow with Python pipelines.']
    };
    this.candidates.push(newCand);
    this.emit('candidates:updated', this.candidates);
  }
}

export const state = new ARPState();
