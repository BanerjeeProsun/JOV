import React from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { ease, spring } from '../../design/motion'

interface WordmarkProps {
  animated?: boolean
  className?: string
  size?: number
}

export const Wordmark: React.FC<WordmarkProps> = ({
  animated = false,
  className = '',
  size = 18,
}) => {
  const reducedMotion = useReducedMotion()
  const letters = ['J', 'O', 'V', '.', 's', 'i']

  if (!animated || reducedMotion) {
    return (
      <span
        className={`font-semibold tracking-[-0.04em] inline-flex items-center text-text ${className}`}
        style={{ fontSize: `${size}px` }}
      >
        <span>JOV</span>
        <span className="text-text inline-block w-[4px] h-[4px] rounded-full mx-[1px] bg-currentColor" style={{ backgroundColor: 'currentColor' }} />
        <span>si</span>
      </span>
    )
  }

  return (
    <span
      className={`font-semibold tracking-[-0.04em] inline-flex items-center text-text ${className}`}
      style={{ fontSize: `${size}px` }}
      aria-label="JOV.si"
    >
      {letters.map((char, index) => {
        if (char === '.') {
          return (
            <motion.span
              key={index}
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.9 + index * 0.04, ...spring.snappy }}
              className="inline-block w-[4px] h-[4px] rounded-full mx-[1px]"
              style={{ backgroundColor: 'currentColor' }}
            />
          )
        }
        return (
          <span key={index} className="inline-block overflow-hidden">
            <motion.span
              className="inline-block"
              initial={{ y: '100%', opacity: 0, filter: 'blur(4px)' }}
              animate={{ y: '0%', opacity: 1, filter: 'blur(0px)' }}
              transition={{
                duration: 0.45,
                delay: 0.85 + index * 0.04,
                ease: ease.out,
              }}
            >
              {char}
            </motion.span>
          </span>
        )
      })}
    </span>
  )
}
