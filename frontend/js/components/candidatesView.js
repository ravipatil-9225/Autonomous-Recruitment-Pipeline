/**
 * Candidates Leaderboard & Detail Component
 * High-density table with rank badges, score breakdown, and detail slide-over.
 */

import { state } from '../state.js';
import { api } from '../api.js';

export function renderCandidatesView(container, onSelectCandidate) {
  function update() {
    const candidates = state.candidates;

    container.innerHTML = `
      <div class="panel-header">
        <div>
          <div class="panel-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" stroke-width="2">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
              <circle cx="9" cy="7" r="4"></circle>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
            </svg>
            Candidate Leaderboard & Evaluation Matrix
          </div>
          <div class="panel-desc">Algorithmic ranking weighted by vector embedding similarity and structured interview rubrics</div>
        </div>
        <div style="display: flex; gap: 10px;">
          <input type="text" id="candidate-search" placeholder="Search skills, name, role…" 
            style="background: var(--bg-surface-elevated); border: 1px solid var(--border-medium); border-radius: var(--radius-md); padding: 6px 12px; color: var(--text-primary); font-size: 13px; outline: none; width: 220px;" />
        </div>
      </div>

      <div class="data-table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width: 60px;">Rank</th>
              <th>Candidate</th>
              <th>Experience & Skills</th>
              <th>Vector Match</th>
              <th>Composite Score</th>
              <th>Status</th>
              <th style="text-align: right;">Actions</th>
            </tr>
          </thead>
          <tbody>
            ${candidates.map(cand => {
              let rankClass = '';
              if (cand.rank === 1) rankClass = 'top-1';
              else if (cand.rank === 2) rankClass = 'top-2';
              else if (cand.rank === 3) rankClass = 'top-3';

              const percentScore = Math.round(cand.scores.final * 100);
              const simPercent = Math.round(cand.scores.similarity * 100);

              return `
                <tr data-id="${cand.id}">
                  <td>
                    <span class="rank-badge ${rankClass}">#${cand.rank}</span>
                  </td>
                  <td>
                    <div style="font-weight: 700; color: var(--text-primary);">${cand.name}</div>
                    <div style="font-size: 12px; color: var(--text-muted);">${cand.email}</div>
                  </td>
                  <td>
                    <div style="font-size: 12.5px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px;">
                      ${cand.years_exp} yrs experience
                    </div>
                    <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                      ${cand.skills.slice(0, 3).map(s => `<span class="tag-badge skill">${s}</span>`).join('')}
                      ${cand.skills.length > 3 ? `<span class="tag-badge">+${cand.skills.length - 3}</span>` : ''}
                    </div>
                  </td>
                  <td>
                    <div style="display: flex; align-items: center; gap: 6px;">
                      <span class="score-number">${simPercent}%</span>
                      <span style="font-size: 11px; color: var(--text-muted);">cosine</span>
                    </div>
                  </td>
                  <td>
                    <div class="score-progress-wrap">
                      <div class="score-bar-bg">
                        <div class="score-bar-fill" style="width: ${percentScore}%;"></div>
                      </div>
                      <span class="score-number" style="color: #38BDF8;">${(cand.scores.final * 100).toFixed(1)}</span>
                    </div>
                  </td>
                  <td>
                    <span class="tag-badge ${cand.recruiter_decision === 'hire' ? 'open' : cand.recruiter_decision === 'no_hire' ? 'closed' : 'draft'}">
                      ${cand.recruiter_decision ? cand.recruiter_decision.toUpperCase() : cand.stage.toUpperCase()}
                    </span>
                  </td>
                  <td style="text-align: right;">
                    <button class="btn btn-secondary btn-sm btn-inspect" data-id="${cand.id}">
                      Inspect Deep Profile
                    </button>
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    `;

    // Add inspect event handlers
    container.querySelectorAll('.btn-inspect').forEach(btn => {
      btn.addEventListener('click', () => {
        const candId = btn.getAttribute('data-id');
        const cand = state.candidates.find(c => c.id === candId);
        if (cand && onSelectCandidate) {
          onSelectCandidate(cand);
        }
      });
    });
  }

  state.subscribe('candidates:updated', update);
  update();
}
