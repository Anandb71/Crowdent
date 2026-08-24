import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('Crowdent operator console', () => {
  it('keeps demo and research boundaries permanently visible', () => {
    render(<App />)

    expect(screen.getByText('DEMO · SYNTHETIC')).toBeInTheDocument()
    expect(screen.getByText('RESEARCH ONLY — NOT DEPLOYMENT CERTIFIED')).toBeInTheDocument()
    expect(screen.getAllByText(/No hardware actuation|No cloud telemetry/i)).not.toHaveLength(0)
  })

  it('shows synchronized baseline and intervention comparisons', () => {
    render(<App />)

    expect(screen.getByText('No action')).toBeInTheDocument()
    expect(screen.getByText('Meter north entry')).toBeInTheDocument()
    expect(screen.getByText(/Common initial ensemble/i)).toBeInTheDocument()
    expect(screen.getByText(/Hypothetical simulation, not a causal claim/i)).toBeInTheDocument()
  })

  it('suppresses countdown and advice when a source becomes stale', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.selectOptions(screen.getByLabelText('Failure injection'), 'stale')

    expect(screen.getByRole('alert')).toHaveTextContent('recommendation suppressed')
    expect(screen.getByText('--:--')).toBeInTheDocument()
    expect(screen.getByText('No recommendation available')).toBeInTheDocument()
    expect(screen.queryByText('Meter north entry to 1.8 people/s')).not.toBeInTheDocument()
  })

  it('requires distinct human lifecycle steps', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Acknowledge review' }))
    expect(screen.getAllByText('ACKNOWLEDGED')).not.toHaveLength(0)

    await user.click(screen.getByRole('button', { name: 'Supervisor accepts advisory' }))
    expect(screen.getAllByText('ACCEPTED')).not.toHaveLength(0)

    await user.click(
      screen.getByRole('button', { name: 'Record human-reported physical action' }),
    )
    expect(screen.getAllByText('PHYSICAL ACTION CONFIRMED')).not.toHaveLength(0)
  })

  it('supports keyboard focus for primary controls', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.tab()
    expect(screen.getByRole('button', { name: 'Pause demo playback' })).toHaveFocus()
  })
})
