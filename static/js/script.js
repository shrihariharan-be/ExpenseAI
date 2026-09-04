/**
 * ExpenseAI - Core JavaScript Engine
 * Production PWA, Responsive UX, Safe Submissions & Charts
 */

const INCOME_CATEGORIES = [
  'Salary',
  'Freelance',
  'Business',
  'Investment',
  'Gift',
  'Other'
];

const EXPENSE_CATEGORIES = [
  'Food',
  'Transportation',
  'Shopping',
  'Entertainment',
  'Bills',
  'Healthcare',
  'Education',
  'Travel',
  'Other'
];

const CATEGORY_COLORS = {
  'Food': '#F97316',
  'Transportation': '#06B6D4',
  'Shopping': '#EC4899',
  'Entertainment': '#8B5CF6',
  'Bills': '#EF4444',
  'Healthcare': '#10B981',
  'Education': '#3B82F6',
  'Travel': '#F59E0B',
  'Salary': '#16A34A',
  'Freelance': '#14B8A6',
  'Business': '#6366F1',
  'Investment': '#84CC16',
  'Gift': '#D946EF',
  'Other': '#64748B'
};

// Handle category dropdown change based on transaction type
function setupCategoryDropdown(typeSelectId, categorySelectId, initialCategory = '') {
  const typeSelect = document.getElementById(typeSelectId);
  const categorySelect = document.getElementById(categorySelectId);

  if (!typeSelect || !categorySelect) return;

  function updateCategories(selectedType, keepValue = '') {
    categorySelect.innerHTML = '<option value="" disabled selected>Choose a category</option>';
    const categories = selectedType === 'Income' ? INCOME_CATEGORIES : EXPENSE_CATEGORIES;

    categories.forEach(cat => {
      const option = document.createElement('option');
      option.value = cat;
      option.textContent = cat;
      if (cat === keepValue) {
        option.selected = true;
      }
      categorySelect.appendChild(option);
    });
  }

  // Initial load
  updateCategories(typeSelect.value, initialCategory);

  // On type change
  typeSelect.addEventListener('change', function () {
    updateCategories(this.value);
  });
}

// Mobile sidebar, drawer, and global interaction handlers
document.addEventListener('DOMContentLoaded', function () {
  const toggleBtn = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('appSidebar');
  const backdrop = document.getElementById('sidebarBackdrop');

  function openSidebar() {
    if (sidebar && backdrop) {
      sidebar.classList.add('show');
      backdrop.classList.add('show');
      document.body.classList.add('body-scroll-locked');
    }
  }

  function closeSidebar() {
    if (sidebar && backdrop) {
      sidebar.classList.remove('show');
      backdrop.classList.remove('show');
      document.body.classList.remove('body-scroll-locked');
    }
  }

  if (toggleBtn && sidebar && backdrop) {
    toggleBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      if (sidebar.classList.contains('show')) {
        closeSidebar();
      } else {
        openSidebar();
      }
    });

    backdrop.addEventListener('click', closeSidebar);

    // Auto-close on Esc key
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && sidebar.classList.contains('show')) {
        closeSidebar();
      }
    });

    // Auto-close when user taps any nav link on mobile/tablet
    const navLinks = sidebar.querySelectorAll('a');
    navLinks.forEach(function (link) {
      link.addEventListener('click', function () {
        if (window.innerWidth < 992) {
          closeSidebar();
        }
      });
    });

    // Global helpers for native Android back button integration
    window.expenseAI = {
      closeActiveDrawer: function () {
        if (sidebar && sidebar.classList.contains('show')) {
          closeSidebar();
          return true;
        }
        return false;
      },
      closeActiveModal: function () {
        const activeModal = document.querySelector('.modal.show');
        if (activeModal && typeof bootstrap !== 'undefined') {
          const bsModal = bootstrap.Modal.getInstance(activeModal) || new bootstrap.Modal(activeModal);
          if (bsModal) {
            bsModal.hide();
            return true;
          }
        }
        return false;
      }
    };
  }

  // Double-submit prevention for all financial POST forms
  const postForms = document.querySelectorAll('form[method="POST"], form[method="post"]');
  postForms.forEach(function (form) {
    if (form.hasAttribute('data-no-double-submit')) return;

    form.addEventListener('submit', function (e) {
      if (!form.checkValidity()) return;

      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn && !submitBtn.disabled) {
        submitBtn.disabled = true;
        const originalHtml = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin me-2"></i> Saving...';

        // Auto-re-enable safety timeout after 8 seconds in case of slow network
        setTimeout(function () {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalHtml;
        }, 8000);
      }
    });
  });

  // Auto-dismiss alerts after 4 seconds
  const alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach(alert => {
    setTimeout(() => {
      try {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
        if (bsAlert) {
          bsAlert.close();
        }
      } catch (e) {
        // Fallback dismissal if bootstrap not ready
        alert.remove();
      }
    }, 4500);
  });
});

/**
 * Chart.js Rendering Functions with Automatic Memory Disposal
 */

// Format numbers as INR currency
function formatCurrency(val) {
  return '₹' + Number(val).toLocaleString('en-IN', {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0
  });
}

// Category Spending Donut Chart
function renderCategoryPieChart(canvasId, labels, data, colors) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  // Destroy existing chart instance to prevent canvas memory leaks
  const existing = Chart.getChart(canvasId);
  if (existing) existing.destroy();

  if (!labels || labels.length === 0) {
    ctx.parentElement.innerHTML = '<div class="empty-state py-4"><i class="fa-solid fa-chart-pie empty-state-icon"></i><p>No expense data available</p></div>';
    return null;
  }

  const backgroundColors = colors && colors.length ? colors : labels.map(l => CATEGORY_COLORS[l] || '#64748B');

  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: backgroundColors,
        borderWidth: 2,
        borderColor: '#ffffff',
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: window.innerWidth < 768 ? 400 : 800
      },
      plugins: {
        legend: {
          position: window.innerWidth < 576 ? 'bottom' : 'bottom',
          labels: {
            boxWidth: 12,
            padding: 12,
            font: { family: "'Inter', sans-serif", size: 11 }
          }
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              const val = context.parsed;
              const total = context.dataset.data.reduce((a, b) => a + b, 0);
              const percentage = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
              return ` ${context.label}: ${formatCurrency(val)} (${percentage}%)`;
            }
          }
        }
      },
      cutout: '68%'
    }
  });
}

// Monthly Income vs Expense Bar Chart
function renderMonthlyBarChart(canvasId, labels, incomeData, expenseData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  const existing = Chart.getChart(canvasId);
  if (existing) existing.destroy();

  if (!labels || labels.length === 0) {
    ctx.parentElement.innerHTML = '<div class="empty-state py-4"><i class="fa-solid fa-chart-column empty-state-icon"></i><p>No monthly data available</p></div>';
    return null;
  }

  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Income',
          data: incomeData,
          backgroundColor: '#16A34A',
          borderRadius: 6,
          barPercentage: 0.6,
          categoryPercentage: 0.6
        },
        {
          label: 'Expense',
          data: expenseData,
          backgroundColor: '#DC2626',
          borderRadius: 6,
          barPercentage: 0.6,
          categoryPercentage: 0.6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: window.innerWidth < 768 ? 400 : 800
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { size: 11 } }
        },
        y: {
          beginAtZero: true,
          grid: { color: '#f1f5f9' },
          ticks: {
            font: { size: 11 },
            callback: function (val) {
              return '₹' + (val >= 1000 ? (val / 1000) + 'k' : val);
            }
          }
        }
      },
      plugins: {
        legend: {
          position: 'top',
          labels: { boxWidth: 12, font: { family: "'Inter', sans-serif", size: 11 } }
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              return ` ${context.dataset.label}: ${formatCurrency(context.parsed.y)}`;
            }
          }
        }
      }
    }
  });
}

// Spending Trend Line Chart
function renderSpendingTrendChart(canvasId, dates, dailyExpenses, cumulativeExpenses) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  const existing = Chart.getChart(canvasId);
  if (existing) existing.destroy();

  if (!dates || dates.length === 0) {
    ctx.parentElement.innerHTML = '<div class="empty-state py-4"><i class="fa-solid fa-chart-line empty-state-icon"></i><p>No spending trend data available</p></div>';
    return null;
  }

  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: dates,
      datasets: [
        {
          label: 'Cumulative Spending',
          data: cumulativeExpenses,
          borderColor: '#2563EB',
          backgroundColor: 'rgba(37, 99, 235, 0.08)',
          fill: true,
          tension: 0.35,
          borderWidth: 2.5,
          pointRadius: 2,
          pointHoverRadius: 6,
          yAxisID: 'y'
        },
        {
          label: 'Daily Expense',
          data: dailyExpenses,
          borderColor: '#F59E0B',
          backgroundColor: 'rgba(245, 158, 11, 0.8)',
          type: 'bar',
          borderRadius: 4,
          barPercentage: 0.4,
          yAxisID: 'y1'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: window.innerWidth < 768 ? 400 : 800
      },
      interaction: {
        mode: 'index',
        intersect: false
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { maxTicksLimit: window.innerWidth < 576 ? 5 : 8, font: { size: 10 } }
        },
        y: {
          type: 'linear',
          display: true,
          position: 'left',
          beginAtZero: true,
          grid: { color: '#f1f5f9' },
          ticks: {
            font: { size: 10 },
            callback: function (val) {
              return '₹' + (val >= 1000 ? (val / 1000) + 'k' : val);
            }
          }
        },
        y1: {
          type: 'linear',
          display: false,
          position: 'right',
          beginAtZero: true,
          grid: { drawOnChartArea: false }
        }
      },
      plugins: {
        legend: {
          position: 'top',
          labels: { boxWidth: 12, font: { family: "'Inter', sans-serif", size: 11 } }
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              return ` ${context.dataset.label}: ${formatCurrency(context.parsed.y)}`;
            }
          }
        }
      }
    }
  });
}

// Income vs Expense Line Chart
function renderIncomeVsExpenseLineChart(canvasId, labels, incomeData, expenseData, savingsData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  const existing = Chart.getChart(canvasId);
  if (existing) existing.destroy();

  if (!labels || labels.length === 0) {
    ctx.parentElement.innerHTML = '<div class="empty-state py-4"><i class="fa-solid fa-chart-line empty-state-icon"></i><p>No data available</p></div>';
    return null;
  }

  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Income',
          data: incomeData,
          borderColor: '#16A34A',
          backgroundColor: 'rgba(22, 163, 74, 0.08)',
          fill: true,
          tension: 0.3,
          borderWidth: 2.5,
          pointRadius: 3,
          pointHoverRadius: 6
        },
        {
          label: 'Expense',
          data: expenseData,
          borderColor: '#DC2626',
          backgroundColor: 'rgba(220, 38, 38, 0.08)',
          fill: true,
          tension: 0.3,
          borderWidth: 2.5,
          pointRadius: 3,
          pointHoverRadius: 6
        },
        {
          label: 'Net Savings',
          data: savingsData,
          borderColor: '#2563EB',
          borderDash: [5, 5],
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 2,
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: window.innerWidth < 768 ? 400 : 800
      },
      interaction: {
        mode: 'index',
        intersect: false
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { size: 11 } }
        },
        y: {
          beginAtZero: true,
          grid: { color: '#f1f5f9' },
          ticks: {
            font: { size: 11 },
            callback: function (val) {
              return '₹' + (val >= 1000 ? (val / 1000) + 'k' : val);
            }
          }
        }
      },
      plugins: {
        legend: {
          position: 'top',
          labels: { boxWidth: 12, font: { family: "'Inter', sans-serif", size: 11 } }
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              return ` ${context.dataset.label}: ${formatCurrency(context.parsed.y)}`;
            }
          }
        }
      }
    }
  });
}
