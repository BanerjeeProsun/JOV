import React, { useState } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { spring } from '../../design/motion'
import { Magnetic } from '../motion/Magnetic'

export interface ButtonProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'onAnimationStart' | 'onAnimationEnd' | 'onAnimationIteration' | 'onDrag' | 'onDragStart' | 'onDragEnd'> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'destructive' | 'danger' | 'coral' | 'blue'
  size?: 'sm' | 'md' | 'lg'
  disabledTooltip?: string
  loading?: boolean
  magnetic?: boolean
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  disabledTooltip,
  disabled = false,
  loading = false,
  magnetic = false,
  className = '',
  ...props
}) => {
  const reducedMotion = useReducedMotion()
  const [isHovered, setIsHovered] = useState(false)

  const sizes = {
    sm: 'px-3.5 py-1.5 text-[13px] h-8',
    md: 'px-5 py-2.5 text-[14px] h-10',
    lg: 'px-6 py-3.5 text-[16px] h-12',
  }

  // Tokens only — monochrome primary ink fill, glass secondary, ghost, destructive
  const baseStyles = {
    primary: 'bg-accent text-accent-contrast border border-transparent shadow-1 hover:opacity-95',
    blue: 'bg-accent text-accent-contrast border border-transparent shadow-1 hover:opacity-95',
    coral: 'bg-accent text-accent-contrast border border-transparent shadow-1 hover:opacity-95',
    secondary: 'bg-bg-elev-1 text-text border border-border hover:bg-bg-elev-2 hover:border-border-strong',
    ghost: 'bg-transparent text-text-2 hover:text-text hover:bg-selected border border-transparent',
    destructive: 'bg-err-subtle text-err border border-err/20 hover:bg-err/20',
    danger: 'bg-err-subtle text-err border border-err/20 hover:bg-err/20',
  }

  const selectedVariant = baseStyles[variant] || baseStyles.primary
  const isInactive = disabled || loading

  const buttonElement = (
    <motion.button
      {...props}
      disabled={isInactive}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      whileTap={isInactive || reducedMotion ? undefined : { scale: 0.97 }}
      transition={spring.snappy}
      className={`relative inline-flex items-center justify-center gap-2 rounded-full font-medium tracking-tight transition-colors duration-150 select-none overflow-hidden ${
        sizes[size]
      } ${selectedVariant} ${isInactive ? 'cursor-not-allowed opacity-45' : ''} ${
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2'
      } ${className}`}
    >
      {/* Primary variant pearl sheen sweep on hover */}
      {(variant === 'primary' || variant === 'blue' || variant === 'coral') && !reducedMotion && !isInactive && isHovered && (
        <motion.span
          className="absolute inset-0 pointer-events-none"
          initial={{ x: '-100%', opacity: 0 }}
          animate={{ x: '100%', opacity: 0.35 }}
          transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
          style={{
            background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.6) 50%, transparent 100%)',
          }}
        />
      )}

      {/* Inline dot-loader when loading: preserve layout width */}
      {loading ? (
        <span className="inline-flex items-center gap-1 py-1" aria-label="Loading">
          <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
          <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse [animation-delay:150ms]" />
          <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse [animation-delay:300ms]" />
        </span>
      ) : (
        children
      )}
    </motion.button>
  )

  const wrapped = magnetic && !isInactive ? (
    <Magnetic strength={6}>{buttonElement}</Magnetic>
  ) : (
    buttonElement
  )

  if (disabled && disabledTooltip) {
    return (
      <span className="group relative inline-flex">
        {wrapped}
        <span className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 hidden w-max max-w-xs -translate-x-1/2 rounded-md glass px-2.5 py-1 text-[11px] text-text border border-border shadow-1 group-hover:block">
          {disabledTooltip}
        </span>
      </span>
    )
  }

  return wrapped
}
