import React from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { ease, dur } from '../../design/motion'

interface SplitTextProps {
  text: string
  className?: string
  accentWords?: string[] // Words to render in Instrument Serif italic
  delay?: number
  as?: 'h1' | 'h2' | 'h3' | 'p' | 'span'
}

export const SplitText: React.FC<SplitTextProps> = ({
  text,
  className = '',
  accentWords = [],
  delay = 0,
  as: Component = 'h1',
}) => {
  const reducedMotion = useReducedMotion()
  const words = text.split(' ')

  const cleanWord = (w: string) => w.replace(/[.,/#!$%^&*;:{}=\-_`~()]/g, '').toLowerCase()

  if (reducedMotion) {
    return (
      <Component className={className} aria-label={text}>
        {words.map((word, i) => {
          const isAccent = accentWords.some(a => cleanWord(a) === cleanWord(word))
          return (
            <span key={i} className={isAccent ? 'font-editorial italic font-normal' : undefined}>
              {word}{i < words.length - 1 ? ' ' : ''}
            </span>
          )
        })}
      </Component>
    )
  }

  return (
    <Component className={className} aria-label={text}>
      {words.map((word, i) => {
        const isAccent = accentWords.some(a => cleanWord(a) === cleanWord(word))
        return (
          <span key={i} className="inline-block overflow-hidden align-top leading-tight mr-[0.25em] last:mr-0">
            <motion.span
              className={`inline-block ${isAccent ? 'font-editorial italic font-normal text-text' : ''}`}
              initial={{ y: '115%', opacity: 0, filter: 'blur(4px)' }}
              animate={{ y: '0%', opacity: 1, filter: 'blur(0px)' }}
              transition={{
                duration: dur.slow,
                delay: delay + i * 0.055,
                ease: ease.out,
              }}
            >
              {word}
            </motion.span>
          </span>
        )
      })}
    </Component>
  )
}
