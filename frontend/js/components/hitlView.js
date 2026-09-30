/**
 * Recruiter HITL (Human-in-the-Loop) Decision Component
 * Allows recruiters to review candidate rankings, inspect interview rubrics,
 * and submit hire/reject decisions with notes.
 */

import { state } from '../state.js';
import { api } from '../api.js';

export function renderHitlView(container, showToast) {
  function update() {
    const candidates = state.candidates;
    const pendingCandidates = candidates.filter(c => !c.recruiter_decision);
    const decidedCandidates = candidates.filter(c => c.recruiter_decision);

    container.innerHTML = `
      <div class="panel-header">
        <div>
          <div class="panel-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--status-warning)" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            Recruiter Human-in-the-Loop (HITL) Decision Center
          </div>
          <div class="panel-desc">Review AI scoring assessments, inspect generated interview rubrics, and approve candidates for final booking</div>
        </div>
        <div class="tag-badge draft" style="font-size: 12px; padding: 4px 10px;">
          ${pendingCandidates.length} Pending Review
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr; gap: 20px;">
        ${pendingCandidates.length === 0 ? `
          <div style="text-align: center; padding: 48px; background: var(--bg-surface-elevated); border-radius: var(--radius-lg); border: 1px solid var(--border-subtle);">
            <div style="font-size: 16px; font-weight: 700; color: var(--status-success); margin-bottom: 6px;">
              ✨ All Pipeline Candidates Reviewed!
            </div>
            <div style="font-size: 13px; color: var(--text-muted);">
              Decisions recorded and synced with PostgreSQL database & automated calendar scheduler.
            </div>
          </div>
        ` : pendingCandidates.map(cand => `
          <div style="background: var(--bg-surface); border: 1px solid var(--border-medium); border-radius: var(--radius-lg); padding: 24px; position: relative;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
              <div>
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
                  <span class="rank-badge top-1">#${cand.rank}</span>
                  <h3 style="font-size: 18px; font-weight: 700;">${cand.name}</h3>
                  <span class="tag-badge skill">${cand.role_applied}</span>
                </div>
                <div style="font-size: 13px; color: var(--text-muted);">
                  ${cand.email} • ${cand.phone} • ${cand.years_exp} Years Experience
                </div>
              </div>
              
              <div style="display: flex; gap: 16px; align-items: center; background: var(--bg-surface-elevated); padding: 8px 16px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
                <div>
                  <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Vector Match</div>
                  <div style="font-size: 15px; font-weight: 800; color: var(--accent-cyan); font-family: var(--font-mono);">${(cand.scores.similarity * 100).toFixed(0)}%</div>
                </div>
                <div style="width: 1px; height: 24px; background: var(--border-subtle);"></div>
                <div>
                  <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Composite Score</div>
                  <div style="font-size: 15px; font-weight: 800; color: #818CF8; font-family: var(--font-mono);">${(cand.scores.final * 100).toFixed(1)} / 100</div>
                </div>
              </div>
            </div>

            <div style="margin-bottom: 16px; background: var(--bg-surface-elevated); border-radius: var(--radius-md); padding: 14px; border: 1px solid var(--border-subtle);">
              <div style="font-size: 12px; font-weight: 700; color: #A5B4FC; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.04em;">
                🎯 AI Evaluation Rationale & Technical Alignment
              </div>
              <p style="font-size: 13.5px; color: var(--text-secondary); line-height: 1.6;">
                ${cand.notes}
              </p>
            </div>

            <div style="margin-bottom: 20px;">
              <div style="font-size: 12px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px;">
                💡 Recommended Deep-Dive Technical Questions
              </div>
              <div style="display: flex; flex-direction: column; gap: 6px;">
                ${cand.interview_questions.map(q => `
                  <div style="font-size: 13px; color: var(--text-secondary); display: flex; gap: 8px; background: rgba(0,0,0,0.2); padding: 8px 12px; border-radius: var(--radius-sm);">
                    <span style="color: var(--accent-primary); font-weight: 700;">•</span>
                    <span>${q}</span>
                  </div>
                `).join('')}
              </div>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-subtle); padding-top: 18px; flex-wrap: wrap; gap: 12px;">
              <div style="flex: 1; min-width: 240px; margin-right: 16px;">
                <input type="text" id="notes-${cand.id}" placeholder="Optional recruiter evaluation notes / feedback…" 
                  style="width: 100%; background: var(--bg-surface-elevated); border: 1px solid var(--border-medium); border-radius: var(--radius-md); padding: 8px 14px; color: var(--text-primary); font-size: 13px; outline: none;" />
              </div>
              
              <div style="display: flex; gap: 10px;">
                <button class="btn btn-danger btn-decision" data-id="${cand.id}" data-decision="no_hire">
                  Reject Candidate
                </button>
                <button class="btn btn-success btn-decision" data-id="${cand.id}" data-decision="hire">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                  Approve & Schedule Interview
                </button>
              </div>
            </div>
          </div>
        `).join('')}
      </div>
    `;

    // Decision click handlers
    container.querySelectorAll('.btn-decision').forEach(btn => {
      btn.addEventListener('click', async () => {
        const candId = btn.getAttribute('data-id');
        const decision = btn.getAttribute('data-decision');
        const notesInput = container.querySelector(`#notes-${candId}`);
        const notes = notesInput ? notesInput.value : '';

        // Record locally
        state.recordCandidateDecision(candId, decision, notes);

        // Sync with API if pipeline run is active
        if (state.activeRun.run_id) {
          try {
            await api.submitDecision(state.activeRun.run_id, decision, notes);
          } catch (e) {
            console.warn('API decision sync error (using local state)', e);
          }
        }

        if (showToast) {
          showToast(
            decision === 'hire' 
              ? `Candidate approved! Outreach agent dispatched interview invitation.` 
              : `Candidate marked as rejected. Status updated in database.`,
            decision === 'hire' ? 'success' : 'info'
          );
        }
      });
    });
  }

  state.subscribe('candidates:updated', update);
  state.subscribe('pipeline:updated', update);
  update();
}
