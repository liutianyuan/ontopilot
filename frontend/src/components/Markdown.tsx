import React from 'react'

interface Props {
  content: string
}

export function Markdown({ content }: Props) {
  const lines = content.split('\n')
  const elements: React.ReactNode[] = []
  let inTable = false
  let tableRows: string[][] = []
  let inCodeBlock = false
  let codeLines: string[] = []
  let codeLang = ''

  const flushTable = (key: string) => {
    if (tableRows.length < 2) return
    const [header, ...bodyRows] = tableRows
    elements.push(
      <div key={key} className="overflow-x-auto my-2">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-gray-100">
              {header.map((h, i) => <th key={i} className="border px-2 py-1 text-left text-gray-600 font-medium">{h.trim()}</th>)}
            </tr>
          </thead>
          <tbody>
            {bodyRows.map((row, ri) => (
              <tr key={ri} className={ri % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                {row.map((cell, ci) => <td key={ci} className="border px-2 py-1 text-gray-700">{renderInline(cell.trim())}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    )
    tableRows = []
  }

  const renderInline = (text: string): React.ReactNode => {
    // **bold**
    const parts: React.ReactNode[] = []
    let last = 0
    const boldRe = /\*\*(.+?)\*\*/g
    let match: RegExpExecArray | null
    let idx = 0
    while ((match = boldRe.exec(text)) !== null) {
      if (match.index > last) parts.push(text.slice(last, match.index))
      parts.push(<strong key={idx++}>{match[1]}</strong>)
      last = boldRe.lastIndex
    }
    if (last < text.length) parts.push(text.slice(last))
    return parts.length > 0 ? <>{parts}</> : text
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const lineKey = `l${i}`

    // Code block
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        elements.push(
          <pre key={lineKey} className="bg-gray-800 text-gray-100 text-xs rounded-lg p-3 my-2 overflow-x-auto">
            <code>{codeLines.join('\n')}</code>
          </pre>,
        )
        codeLines = []
        inCodeBlock = false
      } else {
        inCodeBlock = true
        codeLang = line.slice(3).trim()
      }
      continue
    }
    if (inCodeBlock) {
      codeLines.push(line)
      continue
    }

    // Empty line flushes table
    if (line.trim() === '') {
      if (inTable) { flushTable(lineKey); inTable = false }
      elements.push(<div key={lineKey} className="h-2" />)
      continue
    }

    // Table row
    if (line.startsWith('|') && line.endsWith('|')) {
      // Separator row (|---|---|)
      if (/^[\s|:-]+$/.test(line) && line.includes('-')) continue
      const cells = line.split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1 ? true : idx > 0)
      const actualCells = line.split('|').slice(1, -1)
      tableRows.push(actualCells)
      inTable = true
      continue
    }
    if (inTable) { flushTable(lineKey); inTable = false }

    // Header ###
    if (line.startsWith('### ')) {
      elements.push(<h3 key={lineKey} className="text-base font-semibold text-gray-800 mt-3 mb-1">{renderInline(line.slice(4))}</h3>)
      continue
    }
    if (line.startsWith('## ')) {
      elements.push(<h2 key={lineKey} className="text-lg font-semibold text-gray-800 mt-4 mb-1">{renderInline(line.slice(3))}</h2>)
      continue
    }
    if (line.startsWith('# ')) {
      elements.push(<h1 key={lineKey} className="text-xl font-bold text-gray-800 mt-4 mb-2">{renderInline(line.slice(2))}</h1>)
      continue
    }

    // Unordered list
    if (line.match(/^[-*]\s/)) {
      elements.push(
        <div key={lineKey} className="flex gap-2 text-sm text-gray-800 leading-relaxed">
          <span className="text-gray-400 select-none">•</span>
          <span className="flex-1">{renderInline(line.replace(/^[-*]\s/, ''))}</span>
        </div>,
      )
      continue
    }

    // Ordered list
    const olMatch = line.match(/^\d+[.)]\s/)
    if (olMatch) {
      elements.push(
        <div key={lineKey} className="flex gap-2 text-sm text-gray-800 leading-relaxed">
          <span className="text-gray-400 select-none shrink-0">{olMatch[0]}</span>
          <span className="flex-1">{renderInline(line.slice(olMatch[0].length))}</span>
        </div>,
      )
      continue
    }

    // Regular paragraph
    elements.push(
      <div key={lineKey} className="text-sm text-gray-800 leading-relaxed">
        {renderInline(line)}
      </div>,
    )
  }

  // Flush remaining
  if (inTable) flushTable('end')
  if (inCodeBlock) {
    elements.push(
      <pre key="end" className="bg-gray-800 text-gray-100 text-xs rounded-lg p-3 my-2 overflow-x-auto">
        <code>{codeLines.join('\n')}</code>
      </pre>,
    )
  }

  return <>{elements}</>
}
