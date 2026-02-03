import { useState } from 'react'
import _results from './data/results.json'
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

function App() {
  const [selectedModel, setSelectedModel] = useState<ModelResult | null>(null);

  if (selectedModel) {
    return (
      <div className="min-h-screen bg-gray-900 text-white p-8">
        <button 
          onClick={() => setSelectedModel(null)}
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
                    <td className="p-4 font-mono text-sm">{task.task_id}</td>
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
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <header className="mb-12 text-center">
        <h1 className="text-5xl font-extrabold mb-4 text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-500">
          DrupalBench Dashboard
        </h1>
        <p className="text-gray-400 text-lg">
          Benchmarking LLMs on Drupal 11 Engineering Standards
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {results.map((model: ModelResult) => (
          <div 
            key={model.model_name}
            className="bg-gray-800 rounded-xl p-6 border border-gray-700 hover:border-blue-500 transition cursor-pointer group"
            onClick={() => setSelectedModel(model)}
          >
            <h2 className="text-2xl font-bold mb-4 group-hover:text-blue-400 transition">
              {model.model_name}
            </h2>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-400">pass@1</span>
                <span className="font-semibold">{(model.pass_at_1 * 100).toFixed(1)}%</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div 
                  className="bg-blue-500 h-2 rounded-full" 
                  style={{ width: `${model.pass_at_1 * 100}%` }}
                ></div>
              </div>
              <div className="flex justify-between items-center pt-2">
                <span className="text-gray-400">pass@5</span>
                <span className="font-semibold">{(model.pass_at_5 * 100).toFixed(1)}%</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div 
                  className="bg-purple-500 h-2 rounded-full" 
                  style={{ width: `${model.pass_at_5 * 100}%` }}
                ></div>
              </div>
            </div>
            <div className="mt-6 flex justify-between text-sm text-gray-500">
              <span>{model.total_tasks} Tasks</span>
              <span>{model.total_correct} Correct</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default App
