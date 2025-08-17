"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import type { CallElevatorRequest } from "@/lib/types/elevator"
import { cn } from "@/lib/utils"

interface FloorControlsProps {
  totalFloors: number
  onCallElevator: (request: CallElevatorRequest) => void
  activeCalls: Set<string>
}

export function FloorControls({ totalFloors, onCallElevator, activeCalls }: FloorControlsProps) {
  const [fromFloor, setFromFloor] = useState<number>(1)
  const [toFloor, setToFloor] = useState<number>(1)
  const [isLoading, setIsLoading] = useState<string | null>(null)

  const handleQuickCall = async (floor: number) => {
    const callKey = `1-${floor}`
    setIsLoading(callKey)
    await onCallElevator({ from_floor: 1, to_floor: floor })
    setTimeout(() => setIsLoading(null), 1000)
  }

  const handleCustomCall = async () => {
    if (fromFloor !== toFloor) {
      const callKey = `${fromFloor}-${toFloor}`
      setIsLoading(callKey)
      await onCallElevator({ from_floor: fromFloor, to_floor: toFloor })
      setTimeout(() => setIsLoading(null), 1000)
    }
  }

  const getCallKey = (from: number, to: number) => `${from}-${to}`

  return (
    <div className="space-y-6">
      <Card className="shadow-md hover:shadow-lg transition-shadow duration-200">
        <CardHeader>
          <CardTitle className="text-lg font-bold flex items-center gap-2">🚀 Quick Floor Access</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 gap-3">
            {Array.from({ length: totalFloors }, (_, i) => i + 1).map((floor) => {
              const callKey = getCallKey(1, floor)
              const isActive = activeCalls.has(callKey)
              const isCurrentlyLoading = isLoading === callKey

              return (
                <Button
                  key={floor}
                  variant={isActive ? "default" : "outline"}
                  size="lg"
                  onClick={() => handleQuickCall(floor)}
                  disabled={isActive || isCurrentlyLoading}
                  className={cn(
                    "h-12 text-lg font-bold relative transition-all duration-200 hover:scale-105",
                    isActive && "animate-pulse shadow-lg",
                    isCurrentlyLoading && "animate-bounce",
                  )}
                >
                  {isCurrentlyLoading ? (
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-current" />
                  ) : (
                    <>
                      {floor}
                      {floor === 1 && "🏠"}
                      {floor === totalFloors && "🏢"}
                    </>
                  )}
                  {isActive && <Badge className="absolute -top-2 -right-2 h-5 w-5 p-0 text-xs animate-ping">📡</Badge>}
                </Button>
              )
            })}
          </div>
        </CardContent>
      </Card>

      <Card className="shadow-md hover:shadow-lg transition-shadow duration-200">
        <CardHeader>
          <CardTitle className="text-lg font-bold flex items-center gap-2">🎯 Custom Call</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="from-floor" className="flex items-center gap-1">
                📍 From Floor
              </Label>
              <Input
                id="from-floor"
                type="number"
                min={1}
                max={totalFloors}
                value={fromFloor}
                onChange={(e) => setFromFloor(Number(e.target.value))}
                className="text-center text-lg font-bold transition-all duration-200 hover:scale-105 focus:scale-105"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="to-floor" className="flex items-center gap-1">
                🎯 To Floor
              </Label>
              <Input
                id="to-floor"
                type="number"
                min={1}
                max={totalFloors}
                value={toFloor}
                onChange={(e) => setToFloor(Number(e.target.value))}
                className="text-center text-lg font-bold transition-all duration-200 hover:scale-105 focus:scale-105"
              />
            </div>
          </div>

          {fromFloor !== toFloor && (
            <div className="text-center py-2">
              <div className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                <span className="font-bold">{fromFloor}</span>
                <span className="text-2xl">{fromFloor < toFloor ? "⬆️" : "⬇️"}</span>
                <span className="font-bold">{toFloor}</span>
              </div>
            </div>
          )}

          <Button
            onClick={handleCustomCall}
            disabled={
              fromFloor === toFloor ||
              activeCalls.has(getCallKey(fromFloor, toFloor)) ||
              isLoading === getCallKey(fromFloor, toFloor)
            }
            className={cn(
              "w-full h-12 text-lg font-bold transition-all duration-200 hover:scale-105",
              isLoading === getCallKey(fromFloor, toFloor) && "animate-pulse",
            )}
          >
            {isLoading === getCallKey(fromFloor, toFloor) ? (
              <div className="flex items-center gap-2">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-current" />
                Calling...
              </div>
            ) : (
              <div className="flex items-center gap-2">🚀 Call Elevator</div>
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
