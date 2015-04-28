import codecs
import time
import cPickle
import gzip
import multiprocessing

import modules.token as tk
import modules.perceptron as perceptron

from modules.evaluation import evaluate
from modules.affixes import findAffixes


class posTagger(object):
        
	def __init__(self):
		pass

        #save the model (weight vectors) to a file:
	def save(self, file_name, model):
		stream = gzip.open(file_name, "wb")
		cPickle.dump(model, stream)
		stream.close()
		
         # load the model (weight vectors) from a file:
	def load(self, file_name):
		stream = gzip.open(file_name, "rb")
		model = cPickle.load(stream)
		stream.close()
		return model

	def classifyToken(self,classifier, token, tag, q):
		result = {tag : classifier.classify(token.sparse_feat_vec)}
		q.put(result) 
			

        # train the classifiers using the perceptron algorithm:
	def train(self, file_in, file_out, max_iterations):
		print "\tTraining file: "+file_in

		print "\tExtracting features"
		x0 = time.time()
		feat_vec = self.extractFeatures(file_in)
		x1 = time.time()
		print "\t"+str(len(feat_vec))+" features extracted"
		print "\t\t"+str(x1-x0)+" sec."

		print "\tCreating tokens with feature vectors"
		y0 = time.time()
		tokens = [] # save all instantiated tokens from training data, with finished feature vectors
		tag_set = set() # gather all POS types
		
		# read in sentences from file and generates the corresponding token objects:
		for sentence in tk.sentences(codecs.open(file_in,encoding='utf-8')):

                        # create sparse feature vector representation for each token:
			for t_id, token in enumerate(sentence):
				if t_id == 0: # first token of sentence
					try:
						token.createFeatureVector(feat_vec, sentence[t_id],
                                                                          None, sentence[t_id+1])
					except IndexError: # happens if sentence length is 1
						token.createFeatureVector(feat_vec, sentence[t_id],
                                                                          None, None)
				elif t_id == len(sentence)-1: # last token of sentence
					token.createFeatureVector(feat_vec, sentence[t_id],
                                                                  sentence[t_id-1], None)
				else:
					token.createFeatureVector(feat_vec, sentence[t_id],
                                                                  sentence[t_id-1], sentence[t_id+1])
				tokens.append(token)
				tag_set.add(token.gold_pos)

                y1 = time.time()
		print "\t\t"+str(y1-y0)+" sec."
		
		print "\tCreating and training classifiers"
		z0 = time.time()
		classifiers = {}

		# instantiate a classifier for each pos tag type:
		for tag in tag_set:
			classifiers[tag] = perceptron.classifier(len(feat_vec))

                # train the classifiers:
		for i in range(max_iterations):
			print "\t\tEpoch "+str(i+1)
			for ind, t in enumerate(tokens):
				if ind % (len(tokens)/10) == 0 and not ind == 0:
					print "\t\t\t"+ str(ind) + "/" + str(len(tokens))

				# expand sparse token feature vectors into all dimensions:
				#expanded_feat_vec = t.expandFeatVec(len(feat_vec))
				
				arg_max = ["", 0.0]


				####
				q = multiprocessing.Queue()
				procs = []

				for tag in classifiers:
				    p = multiprocessing.Process(target=self.classifyToken, args=(classifiers[tag], t, tag,q))
				    procs.append(p)
				    p.start()


				results = {}
				for i in range(len(procs)):
				    results.update(q.get())


				for p in procs:
				    p.join()

				argmax = sorted(results.items(), key = lambda x: x[1])[-1]
                                # adjust classifier weights for incorrectly predicted tag and gold tag:
				if argmax[0] != t.gold_pos:
					#classifiers[t.gold_pos].adjust_weights(expanded_feat_vec, True, 0.1)
					#classifiers[arg_max[0]].adjust_weights(expanded_feat_vec, False, 0.1)
                                        classifiers[t.gold_pos].adjust_weights(t.sparse_feat_vec, True, 0.1)
					classifiers[arg_max[0]].adjust_weights(t.sparse_feat_vec, False, 0.1)

                # after training is completed, save classifier vectors (model) to file:
		self.save(file_out, [feat_vec, classifiers])

		z1 = time.time()
		print "\t\t"+str(z1-z0)+" sec."

        # apply the classifiers to test data:
	def test(self, file_in, mod, file_out):

                # load classifier vectors (model) and feature vector from file:

		print "\tLoading the model and the features"
		x0 = time.time()

		model_list = self.load(mod)
		feat_vec = model_list[0]
		classifiers = model_list[1]

		x1 = time.time()
		print "\t"+str(len(feat_vec))+" features loaded"
		print "\t\t"+str(x1-x0)+" sec."

		print "\tTest file: "+file_in

		print "\tCreating tokens with feature vectors"
		y0 = time.time()
		tokens = [] # save all instantiated tokens from training data, with finished feature vectors
		tag_set = set() # gather all POS types
		empty_feat_vec_count = 0
		
		# read in sentences from file and generates the corresponding token objects:
		for sentence in tk.sentences(codecs.open(file_in,encoding='utf-8')):

                        # create sparse feature vector representation for each token:
			for t_id, token in enumerate(sentence):
				if t_id == 0: # first token of sentence
					try:
						token.createFeatureVector(feat_vec, sentence[t_id],
                                                                          None, sentence[t_id+1])
					except IndexError: # happens if sentence length is 1
						token.createFeatureVector(feat_vec, sentence[t_id],
                                                                          None, None)
				elif t_id == len(sentence)-1: # last token of sentence
					token.createFeatureVector(feat_vec, sentence[t_id],
                                                                  sentence[t_id-1], None)
				else:
					token.createFeatureVector(feat_vec, sentence[t_id],
                                                                  sentence[t_id-1], sentence[t_id+1])
				tokens.append(token)
				tag_set.add(token.gold_pos)
				if len(token.sparse_feat_vec) == 0: empty_feat_vec_count+=1

		print "\t\t" + str(empty_feat_vec_count) + " tokens have no features of the feature set"
                y1 = time.time()
		print "\t\t"+str(y1-y0)+" sec."

                print "\tClassifying tokens"
		z0 = time.time()
		output = open(file_out, "w") # temporarily save classification to file for evaluation
		for ind, t in enumerate(tokens):
			if ind % (len(tokens)/10) == 0 and not ind == 0:
                                print "\t\t"+ str(ind) + "/" + str(len(tokens))

                        # expand sparse token feature vectors into all dimensions:
			#expanded_feat_vec = t.expandFeatVec(len(feat_vec))

			arg_max = ["", 0.0]
			for tag in classifiers:
				#temp = classifiers[tag].classify(expanded_feat_vec)
                                temp = classifiers[tag].classify(t.sparse_feat_vec)

				# remember highest classification result:
				if temp > arg_max[1]:
					arg_max[0] = tag
					arg_max[1] = temp

			# set predicted POS tag:
			t.predicted_pos = arg_max[0]

			# print token with predicted POS tag to file:
			print >> output, t.form.encode("utf-8") + "\t" + t.gold_pos.encode("utf-8") + \
                                         "\t" + t.predicted_pos.encode("utf-8")                       
		output.close()
		
		z1 = time.time()
		print "\t\t"+str(z1-z0)+" sec."

        # build mapping of features to vector dimensions (key=feature, value=dimension index):
	def extractFeatures(self, file_in):

		feat_vec = {}
		feat_vec["initial_token"] = len(feat_vec)

                # iterate over all tokens to extract features:
		for sentence in tk.sentences(codecs.open(file_in,encoding='utf-8')):                      
			for token in sentence:

				# POS features:
				"""
				if not "prev_pos_"+str(token.gold_pos) in feat_vec:
                                        feat_vec["prev_pos_"+str(token.gold_pos)] = len(feat_vec.keys())
				if not "prev_pos_"+str(token.predicted_pos) in feat_vec:
                                        feat_vec["prev_pos_"+str(token.predicted_pos)] = len(feat_vec.keys())
				"""
				
				# form features:
				if not "current_form_"+token.form in feat_vec:
                                        feat_vec["current_form_"+token.form] = len(feat_vec)
				if not "prev_form_"+token.form in feat_vec:
                                        feat_vec["prev_form_"+token.form] = len(feat_vec)
				if not "next_form_"+token.form in feat_vec:
                                        feat_vec["next_form_"+token.form] = len(feat_vec)

		return feat_vec

if __name__=='__main__':
        
	t0 = time.time()

	import argparse
	argpar = argparse.ArgumentParser(description='')

	mode = argpar.add_mutually_exclusive_group(required=True)
	mode.add_argument('-feat',dest='features',action='store_true',help='run in feature finding mode')
	mode.add_argument('-train',dest='train',action='store_true',help='run in training mode')
	mode.add_argument('-test',dest='test',action='store_true',help='run in test mode')
	mode.add_argument('-ev',dest='evaluate',action='store_true',help='run in evaluation mode')

	argpar.add_argument('-i','--infile',dest='in_file',help='in file',required=True)
	argpar.add_argument('-e','--epochs',dest='epochs',help='epochs',default='1')
	argpar.add_argument('-m','--model',dest='model',help='model',default='model')
	#argpar.add_argument('-g','--gold',dest='gold',help='gold',required=True)
	#argpar.add_argument('-p','--prediction',dest='prediction',help='prediction',required=True)
	argpar.add_argument('-o','--output',dest='output_file',help='output file',default='output.txt')
	args = argpar.parse_args()

	t = posTagger()

	if args.features:
		print "Running in feature mode\n"
		# find the most frequent prefixes and affixes:
		findAffixes(args.in_file, 5)
	elif args.train:
		print "Running in training mode\n"
		t.train(args.in_file, args.model, int(args.epochs))
	elif args.test:
		print "Running in test mode\n"
		t.test(args.in_file, args.model, args.output_file)
	elif args.evaluate:
		print "Running in evaluation mode\n"
		out_stream = open(args.output_file,'w')
		evaluate(args.in_file, out_stream)
		out_stream.close()

	t1 = time.time()
	print "\n\tDone. Total time: "+ str(t1-t0) + "sec.\n"


