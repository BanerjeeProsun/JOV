import React from 'react'

interface GlassPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
  strong?: boolean
  className?: string
}

export const GlassPanel: React.FC<GlassPanelProps> = ({
  children,
  strong = false,
  className = '',
  ...props
}) => {
  return (
    <div
      {...props}
      className={`${strong ? 'glass-strong' : 'glass'} rounded-card p-6 text-text ${className}`}
    >
      {children}
    </div>
  )
}
