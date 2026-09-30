/**
 * Interactive LangGraph Visualizer Component
 * Displays live pipeline nodes:
 * 1. Parser (S3 Ingestion & De-identification)
 * 2. Screener (Vector Matching & Hard Criteria)
 * 3. Evaluator (Evaluation Agent & Multi-criteria Ranking)
 * 4. Bias Auditor (Four-Fifths Rule & Parity Check)
 * 5. Recruiter Review (HITL Interrupt & Human In The Loop)
 * 6. Scheduler & Outreach (Automated Booking & Cal Invites)
 */

import { state } from '../state.js';
import { api } from '../api.js';

export function renderPipelineVisualizer(container) {
  const nodes = [
    { id: 'parser', name: 'Resume Parser', desc: 'S3 Ingestion & NER Extract' },
    { id: 'screener', name: 'Vector Screener', desc: 'Embeddings & Skills Match' },
    { id: 'evaluator', name: 'Evaluation Agent', desc: 'Multi-criteria Composite' },
    { id: 'bias_audit', name: 'Bias Auditor', desc: '4/5th Rule Parity Guard' },
    { id: 'hitl', name: 'Recruiter Review', desc: 'HITL Human Decision' },
    { id: 'outreach', name: 'Outreach & Cal', desc: 'Calendar Tool & Invite' },
  ];

  function update() {
    const run = state.activeRun;
    const isRunning = run.status === 'running';

    container.innerHTML = `
      <div class="panel-header" style="border-bottom: none; margin-bottom: 8px; padding-bottom: 0;">
        <div>
          <div class="panel-title">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent-primary)" stroke-width="2.2">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
            </svg>
            LangGraph Multi-Agent Orchestrator
            <span class="tag-badge ${run.status === 'completed' ? 'open' : run.status === 'running' ? 'draft' : 'closed'}">
              ${run.status.toUpperCase()}
            </span>
          </div>
          <div class="panel-desc">Stateful acyclic execution graph with human-in-the-loop checkpointing</div>
        </div>
        <div style="display: flex; gap: 10px; align-items: center;">
          <button id="btn-trigger-pipeline" class="btn btn-primary" ${isRunning ? 'disabled' : ''}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
            ${isRunning ? 'Pipeline Executing…' : 'Run Autonomous Pipeline'}
          </button>
        </div>
      </div>

      <div class="dag-flow">
        ${nodes.map((node, index) => {
          let nodeClass = 'dag-node';
          let statusText = 'IDLE';
          let statusBadgeClass = 'status-idle';

          if (run.activeNode === node.id) {
            nodeClass += ' active';
            statusText = 'RUNNING';
            statusBadgeClass = 'status-running';
          } else if (run.status === 'completed') {
            nodeClass += ' completed';
            statusText = 'DONE';
            statusBadgeClass = 'status-done';
          } else if (node.id === 'hitl' && run.activeNode === 'hitl') {
            nodeClass += ' hitl';
            statusText = 'REVIEW';
            statusBadgeClass = 'status-review';
          }

          const hasNext = index < nodes.length - 1;
          const isConnectorActive = isRunning && (run.activeNode === node.id || nodes.findIndex(n => n.id === run.activeNode) > index);

          return `
            <div class="${nodeClass}">
              <div class="dag-node-header">
                <span class="dag-node-title">${node.name}</span>
                <span class="dag-node-status ${statusBadgeClass}">${statusText}</span>
              </div>
              <span class="dag-node-desc">${node.desc}</span>
            </div>
            ${hasNext ? `<div class="dag-connector ${isConnectorActive ? 'active' : ''}"></div>` : ''}
          `;
        }).join('')}
      </div>

      ${run.logs && run.logs.length > 0 ? `
        <div style="margin-top: 14px; background: rgba(0,0,0,0.3); border-radius: var(--radius-md); padding: 10px 14px; border: 1px solid var(--border-subtle);">
          <div style="display: flex; justify-content: space-between; font-size: 11.5px; color: var(--text-muted); margin-bottom: 6px;">
            <span>LIVE EXECUTION TELEMETRY</span>
            <span class="mono">Session ID: ${run.run_id || 'LOCAL-SYNC'}</span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 4px; max-height: 80px; overflow-y: auto;">
            ${run.logs.slice(-4).map(log => `
              <div style="font-size: 12px; font-family: var(--font-mono); color: var(--text-secondary); display: flex; gap: 8px;">
                <span style="color: var(--text-muted);">[${log.time}]</span>
                <span style="color: #818CF8;">[${log.node.toUpperCase()}]</span>
                <span style="color: var(--text-primary);">${log.stage}</span>
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}
    `;

    const btn = container.querySelector('#btn-trigger-pipeline');
    if (btn) {
      btn.addEventListener('click', async () => {
        state.updatePipelineStatus({
          run_id: 'arp-run-' + Date.now().toString(36),
          status: 'running',
          activeNode: 'parser',
          progress: 10,
          summary: { stage: 'Initializing multi-agent pipeline...' }
        });

        // Start WebSocket / Simulation
        api.connectPipelineWS(
          state.activeRun.run_id,
          (msg) => {
            state.updatePipelineStatus(msg);
          },
          (err) => console.warn('WS error', err),
          () => {
            state.updatePipelineStatus({
              status: 'completed',
              activeNode: 'completed',
              summary: { stage: 'Pipeline completed. Candidates ranked & scored.' }
            });
          }
        );
      });
    }
  }

  state.subscribe('pipeline:updated', update);
  state.subscribe('job:selected', update);
  update();
}
