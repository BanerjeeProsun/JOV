import React from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { dur, ease } from '../../design/motion'

interface RevealProps {
  children: React.ReactNode
  delay?: number
  y?: number
  className?: string
  once?: boolean
}

export const Reveal: React.FC<RevealProps> = ({
  children,
  delay = 0,
  y = 16,
  className = '',
  once = true,
}) => {
  const reducedMotion = useReducedMotion()

  if (reducedMotion) {
    return <div className={className}>{children}</div>
  }

  return (
    <motion.div
      initial={{ opacity: 0, y, filter: 'blur(6px)' }}
      whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      viewport={{ once, margin: '-40px' }}
      transition={{ duration: dur.base, delay, ease: ease.out }}
      className={className}
    >
      {children}
    </motion.div>
  )
}
