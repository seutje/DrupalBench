import { useEffect, useMemo, useState } from 'react'
import _results from './data/results.json'
import diagram from './assets/diagram.jpeg'
const results = _results as unknown as ModelResult[];

import './App.css'

interface DomainResult {
  passed: boolean;
  output: string;
}

interface Task {
  task_id: string;
  title: string;
  passed: boolean;
  quality_summary: string;
  domain_results?: Record<string, DomainResult>;
}

interface ModelResult {
  model_name: string;
  total_tasks: number;
  total_samples: number;
  total_correct: number;
  pass_at_1: number;
  pass_at_5: number;
  tasks: Task[];
}

const isSyntheticTaskId = (taskId: string) => taskId.startsWith('syn');

type HistoryState = {
  page: 'home' | 'about' | 'contact';
  modelName?: string;
};

function App() {
  const [selectedModel, setSelectedModel] = useState<ModelResult | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activePage, setActivePage] = useState<'home' | 'about' | 'contact'>('home');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const applyHistoryState = (state?: HistoryState | null) => {
    if (!state || state.page === 'home') {
      setActivePage('home');
      if (state?.modelName) {
        const model = results.find((item) => item.model_name === state.modelName) ?? null;
        setSelectedModel(model);
      } else {
        setSelectedModel(null);
      }
      return;
    }
    setSelectedModel(null);
    setActivePage(state.page);
  };

  const navigateTo = (page: 'home' | 'about' | 'contact') => {
    setSelectedModel(null);
    setActivePage(page);
    setMobileMenuOpen(false);
    window.history.pushState({ page } satisfies HistoryState, '', window.location.href);
  };

  const openModelDetails = (model: ModelResult) => {
    setSelectedModel(model);
    setActivePage('home');
    window.history.pushState(
      { page: 'home', modelName: model.model_name } satisfies HistoryState,
      '',
      window.location.href
    );
  };

  const returnToOverview = () => {
    setSelectedModel(null);
    setActivePage('home');
    window.history.replaceState({ page: 'home' } satisfies HistoryState, '', window.location.href);
  };

  useEffect(() => {
    const handlePopState = (event: PopStateEvent) => {
      applyHistoryState(event.state as HistoryState | null);
    };
    window.addEventListener('popstate', handlePopState);
    if (!window.history.state) {
      window.history.replaceState({ page: 'home' } satisfies HistoryState, '', window.location.href);
    } else {
      applyHistoryState(window.history.state as HistoryState);
    }
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const filteredResults = useMemo(() => {
    if (!searchQuery.trim()) {
      return results;
    }
    const normalizedQuery = normalizeText(searchQuery);
    return results.filter((model) => fuzzyMatch(normalizeText(model.model_name), normalizedQuery));
  }, [searchQuery]);

  if (activePage === 'home' && selectedModel) {
    return (
      <div className="app-shell text-white p-8">
        <button 
          onClick={returnToOverview}
          className="mb-6 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded transition"
        >
          &larr; Back to Overview
        </button>
        
        <header className="mb-8">
          <h1 className="text-4xl font-bold mb-2">{selectedModel.model_name}</h1>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
            <div className="bg-gray-800 p-4 rounded">
              <div className="text-sm text-gray-400">Total Tasks</div>
              <div className="text-2xl font-semibold">{selectedModel.total_tasks}</div>
            </div>
            <div className="bg-gray-800 p-4 rounded">
              <div className="text-sm text-gray-400">Total Correct</div>
              <div className="text-2xl font-semibold">{selectedModel.total_correct}</div>
            </div>
            <div className="bg-gray-800 p-4 rounded">
              <div className="text-sm text-gray-400">pass@1</div>
              <div className="text-2xl font-semibold">{(selectedModel.pass_at_1 * 100).toFixed(1)}%</div>
            </div>
            <div className="bg-gray-800 p-4 rounded">
              <div className="text-sm text-gray-400">pass@5</div>
              <div className="text-2xl font-semibold">{(selectedModel.pass_at_5 * 100).toFixed(1)}%</div>
            </div>
          </div>
        </header>

        <section>
          <h2 className="text-2xl font-bold mb-4">Task Results</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left bg-gray-800 rounded overflow-hidden">
              <thead className="bg-gray-700">
                <tr>
                  <th className="p-4">ID</th>
                  <th className="p-4">Title</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Quality</th>
                </tr>
              </thead>
              <tbody>
                {selectedModel.tasks.map(task => (
                  <tr key={task.task_id} className="border-t border-gray-700">
                    <td className="p-4 font-mono text-sm">
                      {isSyntheticTaskId(task.task_id) ? (
                        task.task_id
                      ) : (
                        <a
                          href={`https://drupal.org/i/${task.task_id}`}
                          className="text-sky-300 hover:text-sky-200 underline"
                          target="_blank"
                          rel="noreferrer"
                        >
                          {task.task_id}
                        </a>
                      )}
                    </td>
                    <td className="p-4">{task.title}</td>
                    <td className="p-4">
                      <div className="flex flex-col space-y-1">
                        <span className={`px-2 py-1 rounded text-xs w-fit ${task.passed ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
                          {task.passed ? 'PASSED' : 'FAILED'}
                        </span>
                        {task.domain_results && Object.entries(task.domain_results).map(([domain, res]) => (
                          <span key={domain} className={`text-[10px] uppercase font-bold ${res.passed ? 'text-green-500' : 'text-red-500'}`}>
                            {domain}: {res.passed ? '✓' : '✗'}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="p-4 text-sm text-gray-400">{task.quality_summary}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="app-shell text-white">
      <div className="app-glow" aria-hidden="true"></div>
      <nav className="app-nav">
        <div className="flex items-center gap-2 font-semibold text-xl text-indigo-200">
          <span className="text-indigo-400">DrupalBench</span>
        </div>
        <div className="hidden md:flex items-center gap-8 text-sm text-slate-200/80">
          <button
            className={`hover:text-white transition ${activePage === 'home' ? 'text-white' : ''}`}
            onClick={() => navigateTo('home')}
          >
            Home
          </button>
          <button
            className={`hover:text-white transition ${activePage === 'about' ? 'text-white' : ''}`}
            onClick={() => navigateTo('about')}
          >
            About
          </button>
          <button
            className={`hover:text-white transition ${activePage === 'contact' ? 'text-white' : ''}`}
            onClick={() => navigateTo('contact')}
          >
            Contact
          </button>
        </div>
        <button
          className="menu-button"
          aria-label="Toggle menu"
          aria-expanded={mobileMenuOpen}
          onClick={() => setMobileMenuOpen((open) => !open)}
        >
          <span></span>
          <span></span>
          <span></span>
        </button>
      </nav>
      {mobileMenuOpen ? (
        <div className="mobile-menu" aria-label="Mobile navigation">
          <button
            className={`hover:text-white transition ${activePage === 'home' ? 'text-white' : ''}`}
            onClick={() => navigateTo('home')}
          >
            Home
          </button>
          <button
            className={`hover:text-white transition ${activePage === 'about' ? 'text-white' : ''}`}
            onClick={() => navigateTo('about')}
          >
            About
          </button>
          <button
            className={`hover:text-white transition ${activePage === 'contact' ? 'text-white' : ''}`}
            onClick={() => navigateTo('contact')}
          >
            Contact
          </button>
        </div>
      ) : null}

      {activePage === 'about' ? (
        <main className="page-content" aria-label="About">
          <img src={diagram} alt="DrupalBench diagram" className="diagram-image" />
        </main>
      ) : null}

      {activePage === 'contact' ? (
        <main className="page-content" aria-label="Contact">
          <div className="contact-card">
            <h2 className="text-2xl font-semibold">Contact</h2>
            <p className="text-slate-200/80 mt-4">Steve De Jonghe</p>
            <p className="text-slate-200/80"><a href="mailto:seutje@gmail.com">seutje@gmail.com</a></p>
            <p className="text-slate-200/80"><a href="https://github.com/seutje/DrupalBench">github.com/seutje/DrupalBench</a></p>
          </div>
        </main>
      ) : null}

      {activePage === 'home' ? (
        <>
          <header className="hero">
            <h1 className="hero-title">DrupalBench</h1>
            <p className="hero-subtitle">
              Benchmarking LLMs on Drupal 11 Engineering Standards
            </p>
          </header>

          <section className="results-section">
            <div className="results-header">
              <div>
                <h2 className="text-2xl md:text-3xl font-semibold">Benchmark Results</h2>
                <p className="text-slate-300/80 mt-2 max-w-2xl">
                  Performance of Large Language Models (LLMs) benchmarked on Drupal 11 engineering standards.
                </p>
              </div>
              <div className="search-wrapper">
                <svg className="search-icon" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    d="M11 4a7 7 0 0 1 5.3 11.7l3 3a1 1 0 0 1-1.4 1.4l-3-3A7 7 0 1 1 11 4Zm0 2a5 5 0 1 0 0 10 5 5 0 0 0 0-10Z"
                    fill="currentColor"
                  />
                </svg>
                <input
                  type="search"
                  placeholder="Search models..."
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  className="search-input"
                />
                <button className="filter-button" aria-label="Filter options">
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path
                      d="M4 6h16M7 12h10M10 18h4"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                    />
                  </svg>
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {filteredResults.map((model: ModelResult) => (
                <div 
                  key={model.model_name}
                  className="glass-card"
                  onClick={() => openModelDetails(model)}
                >
                  <span className="sample-badge">{model.total_samples} samples</span>
                  <h3 className="text-lg md:text-xl font-semibold mb-6 text-white/90 pr-28">
                    {model.model_name}
                  </h3>
                  <div className="space-y-5">
                    <div className="flex justify-between items-center text-sm text-slate-300">
                      <span>pass@1</span>
                      <span className="text-white font-semibold">{(model.pass_at_1 * 100).toFixed(1)}%</span>
                    </div>
                    <div className="progress-track">
                      <div 
                        className="progress-bar progress-blue"
                        style={{ width: `${model.pass_at_1 * 100}%` }}
                      ></div>
                    </div>
                    <div className="flex justify-between items-center text-sm text-slate-300 pt-2">
                      <span>pass@5</span>
                      <span className="text-white font-semibold">{(model.pass_at_5 * 100).toFixed(1)}%</span>
                    </div>
                    <div className="progress-track">
                      <div 
                        className="progress-bar progress-purple"
                        style={{ width: `${model.pass_at_5 * 100}%` }}
                      ></div>
                    </div>
                  </div>
                  <div className="stat-cards">
                    <div className="stat-card">
                      <div className="stat-icon">
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <path
                            d="M6 6h12M6 10h12M6 14h8M6 18h10"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                          />
                        </svg>
                      </div>
                      <div>
                        <span className="stat-value">{model.total_tasks}</span>
                        <span className="stat-label">Tasks</span>
                      </div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-icon success">
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <path
                            d="M9 12.5l2 2 4-4M12 4a8 8 0 1 1 0 16 8 8 0 0 1 0-16Z"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </div>
                      <div>
                        <span className="stat-value">{model.total_correct}</span>
                        <span className="stat-label">Correct</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      ) : null}
    </div>
  )
}

export default App

const normalizeText = (value: string) =>
  value.toLowerCase().replace(/[^a-z0-9]+/g, '');

const fuzzyMatch = (target: string, query: string) => {
  if (!query) {
    return true;
  }
  let targetIndex = 0;
  for (let index = 0; index < query.length; index += 1) {
    const queryChar = query[index];
    targetIndex = target.indexOf(queryChar, targetIndex);
    if (targetIndex === -1) {
      return false;
    }
    targetIndex += 1;
  }
  return true;
};
