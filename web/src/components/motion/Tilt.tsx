import React, { useRef } from 'react'
import { motion, useMotionValue, useSpring, useReducedMotion } from 'motion/react'

interface TiltProps {
  children: React.ReactNode
  maxDegrees?: number
  className?: string
}

export const Tilt: React.FC<TiltProps> = ({
  children,
  maxDegrees = 3,
  className = '',
}) => {
  const ref = useRef<HTMLDivElement>(null)
  const reducedMotion = useReducedMotion()

  const rotateX = useMotionValue(0)
  const rotateY = useMotionValue(0)

  const smoothRotateX = useSpring(rotateX, { stiffness: 220, damping: 25 })
  const smoothRotateY = useSpring(rotateY, { stiffness: 220, damping: 25 })

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (reducedMotion || !ref.current) return
    const rect = ref.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    const centerX = rect.width / 2
    const centerY = rect.height / 2

    const normX = (x - centerX) / centerX
    const normY = (y - centerY) / centerY

    rotateY.set(normX * maxDegrees)
    rotateX.set(-normY * maxDegrees)
  }

  const handleMouseLeave = () => {
    rotateX.set(0)
    rotateY.set(0)
  }

  if (reducedMotion) {
    return <div className={className}>{children}</div>
  }

  return (
    <div style={{ perspective: 1000 }} className={className}>
      <motion.div
        ref={ref}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        style={{
          rotateX: smoothRotateX,
          rotateY: smoothRotateY,
          transformStyle: 'preserve-3d',
        }}
      >
        {children}
      </motion.div>
    </div>
  )
}
