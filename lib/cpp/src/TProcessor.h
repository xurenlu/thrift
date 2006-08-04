#ifndef T_PROCESSOR_H
#define T_PROCESSOR_H

#include <string>
#include <transport/TTransport.h>
#include <boost/shared_ptr.hpp>

namespace facebook { namespace thrift { 

using namespace boost;

using namespace facebook::thrift::transport;

/**
 * A processor is a generic object that acts upon two streams of data, one
 * an input and the other an output. The definition of this object is loose,
 * though the typical case is for some sort of server that either generates
 * responses to an input stream or forwards data from one pipe onto another.
 *
 * @author Mark Slee <mcslee@facebook.com>
 */
class TProcessor {
 public:
  virtual ~TProcessor() {}
  virtual bool process(shared_ptr<TTransport> in, shared_ptr<TTransport> out) = 0;
  virtual bool process(shared_ptr<TTransport> io) { return process(io, io); }
 protected:
  TProcessor() {}
};

}} // facebook::thrift

#endif
