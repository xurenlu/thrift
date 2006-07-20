#if !defined(_concurrency_PosixThreadFactory_h_)
#define _concurrency_PosixThreadFactory_h_ 1

#include "Thread.h"

namespace facebook { namespace thrift { namespace concurrency { 

/** A thread factory to create posix threads 

    @author marc
    @version $Id:$ */

class PosixThreadFactory : public ThreadFactory {

 public:

  /** POSIX Thread scheduler policies */

  enum POLICY {
    OTHER,
    FIFO,
    ROUND_ROBIN
  };

  /** POSIX Thread scheduler relative priorities,
      
      Absolute priority is determined by scheduler policy and OS.  This enumeration specifies relative priorities such that one can
      specify a priority withing a giving scheduler policy without knowing the absolute value of the priority. */

  enum PRIORITY {
    LOWEST = 0,
    LOWER = 1,
    LOW = 2,
    NORMAL = 3,
    HIGH = 4,
    HIGHER = 5,
    HIGHEST = 6,
    INCREMENT = 7,
    DECREMENT = 8
  };

  PosixThreadFactory(POLICY policy=ROUND_ROBIN, PRIORITY priority=NORMAL, int stackSize=1, bool detached=false);

  // From ThreadFactory;

  Thread* newThread(Runnable* runnable) const;

  /** Sets stack size for created threads

     @param value size in megabytes */

  virtual void stackSize(int value);

  /** Gets stack size for created threads

      @return int size in megabytes */

  virtual int stackSize() const;

  /** Sets priority relative to current policy */

  virtual void priority(PRIORITY priority);

  /** Gets priority relative to current policy */

  virtual PRIORITY priority() const;
  
 private:
  
  class Impl;

  Impl* _impl;
};

}}} // facebook::thrift::concurrency

#endif // !defined(_concurrency_PosixThreadFactory_h_)