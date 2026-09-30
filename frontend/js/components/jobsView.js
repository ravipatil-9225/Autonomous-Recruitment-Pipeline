/**
 * Job Requisitions Management Component
 * Allows creating, listing, publishing, and closing job requisitions.
 */

import { state } from '../state.js';
import { api } from '../api.js';

export function renderJobsView(container, showToast, openJobModal) {
  function update() {
    const jobs = state.jobs;

    container.innerHTML = `
      <div class="panel-header">
        <div>
          <div class="panel-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent-primary)" stroke-width="2">
              <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
              <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
            </svg>
            Job Requisitions & Requirements
          </div>
          <div class="panel-desc">Manage open positions, configure embedding targets, and trigger batch screening</div>
        </div>
        <button id="btn-create-job" class="btn btn-primary">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          Create Job Requisition
        </button>
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 18px;">
        ${jobs.map(job => `
          <div style="background: var(--bg-surface); border: 1px solid var(--border-medium); border-radius: var(--radius-lg); padding: 20px; display: flex; flex-direction: column; justify-content: space-between; gap: 14px; position: relative;">
            <div>
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <span class="tag-badge ${job.status === 'open' ? 'open' : job.status === 'draft' ? 'draft' : 'closed'}">
                  ${job.status.toUpperCase()}
                </span>
                <span style="font-size: 11.5px; color: var(--text-muted);">
                  ${new Date(job.created_at).toLocaleDateString()}
                </span>
              </div>
              <h3 style="font-size: 16px; font-weight: 700; color: var(--text-primary); margin-bottom: 6px;">
                ${job.title}
              </h3>
              <div style="font-size: 12.5px; color: var(--text-muted); display: flex; flex-direction: column; gap: 2px;">
                <span>🏢 ${job.department || 'Engineering'}</span>
                <span>📍 ${job.location || 'Remote'}</span>
              </div>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-subtle); padding-top: 12px;">
              <button class="btn btn-secondary btn-sm btn-select-job" data-id="${job.id}">
                ${state.activeJobId === job.id ? '✓ Active Focus' : 'Select Requisition'}
              </button>
              
              <div style="display: flex; gap: 6px;">
                ${job.status === 'draft' ? `
                  <button class="btn btn-success btn-sm btn-publish" data-id="${job.id}">Publish</button>
                ` : job.status === 'open' ? `
                  <button class="btn btn-secondary btn-sm btn-close" data-id="${job.id}">Close</button>
                ` : ''}
              </div>
            </div>
          </div>
        `).join('')}
      </div>
    `;

    const createBtn = container.querySelector('#btn-create-job');
    if (createBtn) {
      createBtn.addEventListener('click', () => openJobModal());
    }

    container.querySelectorAll('.btn-select-job').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-id');
        state.setActiveJob(id);
        if (showToast) showToast('Active requisition switched!', 'info');
      });
    });

    container.querySelectorAll('.btn-publish').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        const job = state.jobs.find(j => j.id === id);
        if (job) {
          job.status = 'open';
          state.setJobs([...state.jobs]);
          if (showToast) showToast(`Requisition "${job.title}" published!`, 'success');
        }
      });
    });

    container.querySelectorAll('.btn-close').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        const job = state.jobs.find(j => j.id === id);
        if (job) {
          job.status = 'closed';
          state.setJobs([...state.jobs]);
          if (showToast) showToast(`Requisition "${job.title}" closed.`, 'info');
        }
      });
    });
  }

  state.subscribe('jobs:updated', update);
  state.subscribe('job:selected', update);
  update();
}
