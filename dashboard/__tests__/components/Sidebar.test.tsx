import React from 'react';
import { render, screen } from '@testing-library/react';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  usePathname: () => '/',
}));

// Mock lucide-react icons
jest.mock('lucide-react', () => ({
  MessageSquare: () => <span data-testid="icon-message" />,
  PenTool: () => <span data-testid="icon-pen" />,
  Play: () => <span data-testid="icon-play" />,
  Radio: () => <span data-testid="icon-radio" />,
  Settings: () => <span data-testid="icon-settings" />,
  Shield: () => <span data-testid="icon-shield" />,
}));

import Sidebar from '@/components/Sidebar';

describe('Sidebar', () => {
  it('renders the brand name', () => {
    render(<Sidebar />);
    expect(screen.getByText('Raahi')).toBeInTheDocument();
  });

  it('renders all navigation items', () => {
    render(<Sidebar />);
    expect(screen.getByText('Event Setup')).toBeInTheDocument();
    expect(screen.getByText('Floor Planner')).toBeInTheDocument();
    expect(screen.getByText('Simulator')).toBeInTheDocument();
    expect(screen.getByText('Live Monitoring')).toBeInTheDocument();
  });

  it('renders navigation links with correct hrefs', () => {
    render(<Sidebar />);
    const links = screen.getAllByRole('link');
    const hrefs = links.map((l) => l.getAttribute('href'));
    expect(hrefs).toContain('/');
    expect(hrefs).toContain('/floor-planner');
    expect(hrefs).toContain('/visualizer');
    expect(hrefs).toContain('/monitoring');
  });

  it('shows "Soon" badge on Live Monitoring', () => {
    render(<Sidebar />);
    expect(screen.getByText('Soon')).toBeInTheDocument();
  });

  it('highlights the active route', () => {
    render(<Sidebar />);
    // Home "/" is the active route based on our mock
    const homeLink = screen.getByText('Event Setup').closest('a');
    expect(homeLink?.className).toContain('bg-white');
  });

  it('renders the version footer', () => {
    render(<Sidebar />);
    expect(screen.getByText(/v1\.0\.0/)).toBeInTheDocument();
  });
});
