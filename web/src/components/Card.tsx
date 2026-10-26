import React from 'react'
import { motion, useReducedMotion } from 'motion/react'

interface CardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onAnimationStart' | 'onAnimationEnd' | 'onAnimationIteration'> { variant?: 'default' | 'recessed' | 'coral' | 'floating'; interactive?: boolean }

export const Card: React.FC<CardProps> = ({ children, variant = 'default', interactive = false, className = '', ...props }) => {
  const reducedMotion = useReducedMotion()
  const surface = variant === 'recessed' ? 'bg-ash' : variant === 'coral' ? 'bg-warning-subtle' : 'bg-surface'
  return <motion.div layout={interactive} whileHover={interactive && !reducedMotion ? { y: -2 } : undefined} transition={{ type: 'spring', stiffness: 420, damping: 30 }}><div {...props} className={`rounded-card-lg p-7 ${surface} ${interactive ? 'cursor-pointer transition-colors duration-150 hover:bg-ash' : ''} ${className}`}>{children}</div></motion.div>
}
