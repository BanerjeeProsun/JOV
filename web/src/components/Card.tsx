import React from 'react'
import { motion, useReducedMotion } from 'motion/react'

interface CardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onAnimationStart' | 'onAnimationEnd' | 'onAnimationIteration'> {
  variant?: 'default' | 'elevated' | 'recessed' | 'warning'
  interactive?: boolean
}

export const Card: React.FC<CardProps> = ({
  children,
  variant = 'default',
  interactive = false,
  className = '',
  ...props
}) => {
  const reducedMotion = useReducedMotion()

  const surface =
    variant === 'recessed'
      ? 'bg-bg-elev-2'
      : variant === 'elevated'
      ? 'bg-bg-elev-1 shadow-1'
      : variant === 'warning'
      ? 'bg-warn-subtle border-warn'
      : 'bg-bg-elev-1'

  return (
    <motion.div
      layout={interactive}
      whileHover={interactive && !reducedMotion ? { y: -2 } : undefined}
      transition={{ type: 'spring', stiffness: 420, damping: 30 }}
      className="h-full"
    >
      <div
        {...props}
        className={`rounded-card p-6 border border-border text-text ${surface} ${
          interactive ? 'cursor-pointer transition-colors duration-150 hover:bg-bg-elev-2' : ''
        } ${className}`}
      >
        {children}
      </div>
    </motion.div>
  )
}
